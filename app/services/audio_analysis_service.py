"""
Real-time audio analysis service using Azure Speech Pronunciation Assessment.

Manages per-participant Azure Speech sessions during live arena sessions.
Feeds audio chunks into Azure's PushAudioInputStream for streaming pronunciation
assessment, collects incremental results, and generates LLM feedback summaries
via AWS Bedrock.

Architecture:
  Frontend (AudioWorklet) -> binary WS frames -> this service -> Azure Speech SDK
  Azure results -> broadcast ai_analysis event via WebSocket -> teacher panel
"""

import asyncio
import json
import logging
import random
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple
from uuid import UUID

import azure.cognitiveservices.speech as speechsdk

from app.config import settings

logger = logging.getLogger(__name__)

# Azure Speech PCM format: 16kHz, 16-bit, mono
SAMPLE_RATE = 16000
BITS_PER_SAMPLE = 16
CHANNELS = 1

# Throttle: broadcast analysis at most every N seconds per participant
ANALYSIS_BROADCAST_INTERVAL_SECONDS = 5

# Throttle: generate LLM feedback summary at most every N seconds per participant
FEEDBACK_SUMMARY_INTERVAL_SECONDS = 10

# Azure locale mapping from our language codes to Azure locale codes.
# Language.code in our DB is ISO 639-1 (e.g. "en", "fr", "es").
# Azure requires full locale (e.g. "en-US", "fr-FR").
# We map to a sensible default locale per language code.
LANGUAGE_CODE_TO_AZURE_LOCALE = {
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "ru": "ru-RU",
    "ar": "ar-SA",
    "zh": "zh-CN",
    "pt": "pt-BR",
    "de": "de-DE",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "hi": "hi-IN",
    "vi": "vi-VN",
    "th": "th-TH",
    "sv": "sv-SE",
    "da": "da-DK",
    "fi": "fi-FI",
    "nb": "nb-NO",
    "ca": "ca-ES",
    "ms": "ms-MY",
    "ta": "ta-IN",
}


@dataclass
class WordResult:
    """Pronunciation result for a single word."""
    word: str
    accuracy_score: float
    error_type: str  # "None", "Mispronunciation", "Omission", "Insertion"
    substitution: Optional[str] = None  # e.g. "said /s/ for /θ/" — from NBestPhonemes


@dataclass
class AnalysisResult:
    """Aggregated pronunciation analysis for a participant."""
    accuracy_score: float = 0.0
    fluency_score: float = 0.0
    pronunciation_score: float = 0.0
    prosody_score: Optional[float] = None  # Only en-US
    words: List[WordResult] = field(default_factory=list)
    feedback_summary: Optional[str] = None
    language: str = "en-US"
    timestamp: float = 0.0


@dataclass
class ParticipantAudioSession:
    """Manages an Azure Speech session for one participant."""
    arena_id: UUID
    user_id: UUID
    language_locale: str
    push_stream: speechsdk.audio.PushAudioInputStream
    speech_recognizer: speechsdk.SpeechRecognizer
    latest_result: AnalysisResult = field(default_factory=AnalysisResult)
    last_broadcast_time: float = 0.0
    last_feedback_time: float = 0.0
    _recognizing: bool = False
    # Accumulate words across recognition events for rolling window
    _recent_words: List[WordResult] = field(default_factory=list)
    _recent_accuracy_scores: List[float] = field(default_factory=list)
    _recent_fluency_scores: List[float] = field(default_factory=list)
    _recent_pronunciation_scores: List[float] = field(default_factory=list)
    # Last 3 tips sent — passed to prompt to prevent repetition (bounded deque, O(1) pops)
    _recent_tips: Deque[str] = field(default_factory=lambda: deque(maxlen=3))
    # Snapshot of accuracy 30s ago for trend detection
    _accuracy_snapshot: float = 0.0
    _accuracy_snapshot_time: float = 0.0


class AudioAnalysisService:
    """
    Manages all participant audio analysis sessions for arena live sessions.

    Thread safety: Azure Speech SDK runs callbacks on its own threads.
    We use asyncio-safe patterns to bridge SDK callbacks to the async world.
    """

    def __init__(self):
        # {(arena_id, user_id): ParticipantAudioSession}
        self._sessions: Dict[Tuple[UUID, UUID], ParticipantAudioSession] = {}
        # Callback for broadcasting results (set by WebSocket handler)
        self._broadcast_callback = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Persistent aioboto3 session — created once, reuses TLS connections across calls.
        # The actual client context is opened lazily on first feedback call and held open.
        import aioboto3
        from aiobotocore.config import AioConfig
        self._boto_session = aioboto3.Session()
        self._bedrock_client_ctx = None  # opened on first use, never closed
        self._bedrock_client = None

        # Adaptive retry config: botocore maintains a client-side token bucket
        # that slows outgoing requests automatically when throttling is observed.
        self._aioboto_config = AioConfig(
            region_name=settings.AWS_REGION,
            retries={"max_attempts": 8, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=15,
        )

        # Global semaphore: caps in-flight Bedrock calls across all sessions.
        # At 10s/participant, 15 concurrent participants ≈ 90 RPM — within default quotas.
        self._bedrock_semaphore = asyncio.Semaphore(15)

    async def _get_bedrock_client(self):
        """Lazy-open a persistent Bedrock client — reuses the same TLS connection."""
        if self._bedrock_client is None:
            self._bedrock_client_ctx = self._boto_session.client(
                "bedrock-runtime", config=self._aioboto_config
            )
            self._bedrock_client = await self._bedrock_client_ctx.__aenter__()
        return self._bedrock_client

    def set_broadcast_callback(self, callback):
        """Set the async callback for broadcasting analysis results.

        Signature: async def callback(arena_id: UUID, data: dict) -> None
        """
        self._broadcast_callback = callback

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop, caching it for use from SDK callback threads.

        Must be called from within a running async context (i.e. from start_session).
        Uses get_running_loop() which is the correct Python 3.10+ API and guarantees
        we capture the actual uvicorn event loop, not a stale one.
        """
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def start_session(
        self,
        arena_id: UUID,
        user_id: UUID,
        language_code: str,
        student_name: str = "",
    ) -> bool:
        """
        Initialize an Azure Speech pronunciation assessment session for a participant.

        Args:
            arena_id: The arena ID
            user_id: The participant's user ID
            language_code: ISO 639-1 language code from Language.code (e.g. "en", "fr")
            student_name: Display name for broadcast events

        Returns:
            True if session started successfully, False otherwise
        """
        key = (arena_id, user_id)
        if key in self._sessions:
            return True  # Already running

        if not settings.AZURE_SPEECH_KEY:
            logger.error("azure_speech_key_not_configured")
            return False

        locale = LANGUAGE_CODE_TO_AZURE_LOCALE.get(language_code, "en-US")

        try:
            # Configure Azure Speech
            speech_config = speechsdk.SpeechConfig(
                subscription=settings.AZURE_SPEECH_KEY,
                region=settings.AZURE_SPEECH_REGION,
            )
            speech_config.speech_recognition_language = locale

            # Configure pronunciation assessment
            pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True,  # P1: unlocks Omission/Insertion error types
            )
            # Enable prosody for en-US (only supported locale)
            if locale == "en-US":
                pronunciation_config.enable_prosody_assessment()
            # P2: return top-5 probable phonemes so we know what learner actually said
            pronunciation_config.nbest_phoneme_count = 5

            # Create push stream for feeding audio chunks
            audio_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=SAMPLE_RATE,
                bits_per_sample=BITS_PER_SAMPLE,
                channels=CHANNELS,
            )
            push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

            # Create recognizer
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )

            # Apply pronunciation assessment to recognizer
            pronunciation_config.apply_to(recognizer)

            # Create session
            session = ParticipantAudioSession(
                arena_id=arena_id,
                user_id=user_id,
                language_locale=locale,
                push_stream=push_stream,
                speech_recognizer=recognizer,
                latest_result=AnalysisResult(language=locale),
            )

            # Cache the event loop for SDK callbacks
            self._get_or_create_loop()

            # Wire up SDK callbacks
            recognizer.recognized.connect(
                lambda evt, s=session, name=student_name: self._on_recognized(evt, s, name)
            )
            recognizer.canceled.connect(
                lambda evt, s=session: self._on_canceled(evt, s)
            )

            # Start continuous recognition
            recognizer.start_continuous_recognition_async()
            session._recognizing = True

            self._sessions[key] = session

            logger.info(
                "audio_analysis_session_started",
                extra={
                    "arena_id": str(arena_id),
                    "user_id": str(user_id),
                    "locale": locale,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "audio_analysis_session_start_failed",
                extra={
                    "arena_id": str(arena_id),
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )
            return False

    async def process_audio_chunk(
        self, arena_id: UUID, user_id: UUID, audio_data: bytes
    ) -> None:
        """
        Feed raw PCM audio into the participant's Azure Speech session.

        Args:
            arena_id: The arena ID
            user_id: The participant's user ID
            audio_data: Raw PCM audio bytes (16kHz, 16-bit, mono)
        """
        key = (arena_id, user_id)
        session = self._sessions.get(key)
        if not session:
            return

        try:
            session.push_stream.write(audio_data)
        except Exception as e:
            logger.warning(
                "audio_chunk_write_failed",
                extra={
                    "arena_id": str(arena_id),
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )

    def _on_recognized(
        self, evt: speechsdk.SpeechRecognitionEventArgs, session: ParticipantAudioSession, student_name: str
    ):
        """
        SDK callback when a speech segment is recognized (runs on SDK thread).
        Extracts pronunciation assessment results and schedules broadcast.
        """
        result = evt.result
        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return

        try:
            # Parse scores from raw JSON — stable across all SDK versions.
            # PronunciationAssessmentResult wrapper accesses private attrs that
            # can be absent when the result lacks NBest/PronunciationAssessment data.
            import json as _json
            raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
            if not raw_json:
                return

            resp = _json.loads(raw_json)
            nbest = resp.get("NBest", [])
            if not nbest:
                return

            pron = nbest[0].get("PronunciationAssessment", {})
            accuracy = float(pron.get("AccuracyScore", 0.0))
            fluency = float(pron.get("FluencyScore", 0.0))
            pronunciation = float(pron.get("PronScore", 0.0))
            prosody = float(pron["ProsodyScore"]) if "ProsodyScore" in pron else None

            # Extract word-level results with phoneme substitution patterns
            words = []
            for w in nbest[0].get("Words", []):
                w_pron = w.get("PronunciationAssessment", {})
                error_type = w_pron.get("ErrorType", "None")

                # P2: find most likely substitution from NBestPhonemes on mispronounced phonemes.
                # Dual-threshold guard: require both word-level < 65 AND phoneme-level < 45
                # to avoid noisy false substitutions from background/mic artefacts.
                substitution = None
                if error_type == "Mispronunciation" and float(w_pron.get("AccuracyScore", 100)) < 65:
                    for phoneme in w.get("Phonemes", []):
                        p_pron = phoneme.get("PronunciationAssessment", {})
                        if p_pron.get("AccuracyScore", 100) < 45:
                            nbest_phonemes = p_pron.get("NBestPhonemes", [])
                            expected = phoneme.get("Phoneme", "")
                            if nbest_phonemes and expected:
                                # Top-1 is what they actually produced
                                actual = nbest_phonemes[0].get("Phoneme", "")
                                if actual and actual != expected:
                                    substitution = f"/{actual}/ for /{expected}/"
                                    break  # report first problematic phoneme per word

                words.append(WordResult(
                    word=w.get("Word", ""),
                    accuracy_score=float(w_pron.get("AccuracyScore", 0.0)),
                    error_type=error_type,
                    substitution=substitution,
                ))

            # Update rolling window
            session._recent_words.extend(words)
            # Keep last 50 words
            session._recent_words = session._recent_words[-50:]

            session._recent_accuracy_scores.append(accuracy)
            session._recent_fluency_scores.append(fluency)
            session._recent_pronunciation_scores.append(pronunciation)
            # Keep last 10 scores for averaging
            session._recent_accuracy_scores = session._recent_accuracy_scores[-10:]
            session._recent_fluency_scores = session._recent_fluency_scores[-10:]
            session._recent_pronunciation_scores = session._recent_pronunciation_scores[-10:]

            # Average over rolling window
            avg_accuracy = sum(session._recent_accuracy_scores) / len(session._recent_accuracy_scores)
            avg_fluency = sum(session._recent_fluency_scores) / len(session._recent_fluency_scores)
            avg_pronunciation = sum(session._recent_pronunciation_scores) / len(session._recent_pronunciation_scores)

            # P3: update 30s accuracy snapshot for trend detection
            now = time.time()
            if session._accuracy_snapshot_time == 0.0:
                session._accuracy_snapshot = avg_accuracy
                session._accuracy_snapshot_time = now
            elif now - session._accuracy_snapshot_time >= 30.0:
                session._accuracy_snapshot = avg_accuracy
                session._accuracy_snapshot_time = now

            session.latest_result = AnalysisResult(
                accuracy_score=round(avg_accuracy, 1),
                fluency_score=round(avg_fluency, 1),
                pronunciation_score=round(avg_pronunciation, 1),
                prosody_score=round(prosody, 1) if prosody is not None else None,
                words=list(session._recent_words[-10:]),
                language=session.language_locale,
                timestamp=now,
            )

            # Throttle broadcast
            now = time.time()
            if now - session.last_broadcast_time >= ANALYSIS_BROADCAST_INTERVAL_SECONDS:
                session.last_broadcast_time = now
                self._schedule_broadcast(session, student_name)

        except Exception as e:
            logger.error(
                "pronunciation_result_processing_failed",
                extra={
                    "arena_id": str(session.arena_id),
                    "user_id": str(session.user_id),
                    "error": str(e),
                },
            )

    def _on_canceled(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs, session: ParticipantAudioSession):
        """SDK callback when recognition is canceled."""
        logger.warning(
            "speech_recognition_canceled",
            extra={
                "arena_id": str(session.arena_id),
                "user_id": str(session.user_id),
                "reason": str(evt.cancellation_details.reason),
                "error_details": evt.cancellation_details.error_details,
            },
        )

    def _schedule_broadcast(self, session: ParticipantAudioSession, student_name: str):
        """Schedule an async broadcast from the Azure SDK callback thread."""
        if not self._broadcast_callback or not self._loop:
            return

        if self._loop.is_closed():
            logger.warning("analysis_broadcast_skipped_loop_closed", extra={"user_id": str(session.user_id)})
            return

        result = session.latest_result
        data = {
            "event_type": "ai_analysis",
            "data": {
                "user_id": str(session.user_id),
                "student_name": student_name,
                "accuracy_score": result.accuracy_score,
                "fluency_score": result.fluency_score,
                "prosody_score": result.prosody_score,
                "pronunciation_score": result.pronunciation_score,
                "words": [
                    {
                        "word": w.word,
                        "accuracy": w.accuracy_score,
                        "error_type": w.error_type,
                        **({"substitution": w.substitution} if w.substitution else {}),
                    }
                    for w in result.words
                ],
                "feedback_summary": result.feedback_summary,
                "language": result.language,
            },
        }

        # Check if we should generate LLM feedback
        now = time.time()
        should_generate_feedback = (
            now - session.last_feedback_time >= FEEDBACK_SUMMARY_INTERVAL_SECONDS
            and len(session._recent_words) >= 3
        )

        coro = (
            self._generate_and_broadcast(session, data, student_name)
            if should_generate_feedback
            else self._broadcast_callback(session.arena_id, data)
        )
        if should_generate_feedback:
            session.last_feedback_time = now

        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)

            def _on_done(fut: "asyncio.Future[None]") -> None:
                try:
                    fut.result()
                except Exception as exc:
                    logger.error(
                        "analysis_broadcast_failed",
                        extra={"user_id": str(session.user_id), "error": str(exc)},
                    )

            future.add_done_callback(_on_done)
        except RuntimeError as exc:
            logger.error(
                "analysis_broadcast_schedule_failed",
                extra={"user_id": str(session.user_id), "error": str(exc)},
            )

    async def _generate_and_broadcast(
        self, session: ParticipantAudioSession, data: dict, student_name: str
    ):
        """Generate LLM feedback summary and broadcast the result."""
        try:
            feedback = await self._generate_feedback_summary(session)
            if feedback:
                session.latest_result.feedback_summary = feedback
                data["data"]["feedback_summary"] = feedback
        except Exception as e:
            logger.warning(
                "feedback_generation_failed",
                extra={"user_id": str(session.user_id), "error": str(e)},
            )

        if self._broadcast_callback:
            await self._broadcast_callback(session.arena_id, data)

    # P4: static system prompt — cached by Bedrock, never resent as tokens after first call
    _COACHING_SYSTEM_PROMPT = (
        "You are a real-time pronunciation coach for language learners. "
        "You receive structured JSON pronunciation data and return ONE coaching tip.\n\n"
        "Rules:\n"
        "- 1-2 sentences maximum, max 30 words total\n"
        "- Be specific: name the exact word or sound that needs work\n"
        "- Coach toward being understood, not sounding like a native speaker\n"
        "- If recent_tips contains similar advice, address a DIFFERENT area\n"
        "- Tone: direct and encouraging — no filler like 'Great job!' or 'Keep it up!'\n"
        "- For Omission errors: coach completeness/rhythm\n"
        "- For Insertion errors: coach smoothness/not adding sounds\n"
        "- For Mispronunciation with substitution: name the specific sound swap\n"
        "- If fluency < 60: focus on pausing/rhythm over individual sounds\n\n"
        "Respond with plain text only — just the coaching tip, nothing else."
    )

    async def _generate_feedback_summary(self, session: ParticipantAudioSession) -> Optional[str]:
        """Generate a coaching tip using Bedrock Nova Lite with enriched prompt data."""
        words = session._recent_words[-15:]
        if not words:
            return None

        result = session.latest_result

        # Build word details with error types and substitutions
        word_entries = []
        for w in words[-10:]:
            entry = f'"{w.word}" ({w.accuracy_score:.0f}%'
            if w.error_type != "None":
                entry += f", {w.error_type}"
            if w.substitution:
                entry += f", said {w.substitution}"
            entry += ")"
            word_entries.append(entry)

        # P3: compute trend
        delta = result.accuracy_score - session._accuracy_snapshot
        if abs(delta) < 3:
            trend = "stable"
        elif delta > 0:
            trend = f"improving (+{delta:.0f}pts)"
        else:
            trend = f"declining ({delta:.0f}pts)"

        # Build lean user payload (variable data only)
        import json as _json
        payload = {
            "language": session.language_locale,
            "accuracy": result.accuracy_score,
            "fluency": result.fluency_score,
            "trend": trend,
            "words": ", ".join(word_entries),
            "recent_tips": session._recent_tips[-2:],  # P3: prevent repetition
        }
        if result.prosody_score is not None:
            payload["prosody"] = result.prosody_score

        user_content = _json.dumps(payload, ensure_ascii=False)

        from botocore.exceptions import ClientError
        _RETRYABLE = {"ThrottlingException", "ServiceUnavailableException",
                      "ModelTimeoutException", "InternalServerException"}

        for attempt in range(5):
            try:
                async with self._bedrock_semaphore:
                    bedrock = await self._get_bedrock_client()
                    response = await bedrock.converse(
                        modelId=settings.BEDROCK_MODEL_ID,
                        system=[{"text": self._COACHING_SYSTEM_PROMPT}],
                        messages=[{"role": "user", "content": [{"text": user_content}]}],
                        inferenceConfig={"maxTokens": 80, "temperature": 0.7},
                    )

                text = response["output"]["message"]["content"][0]["text"].strip()
                if len(text) > 250:
                    text = text[:247] + "..."

                # deque(maxlen=3) handles eviction automatically — no pop(0) needed
                session._recent_tips.append(text)
                return text

            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code not in _RETRYABLE or attempt == 4:
                    logger.warning("bedrock_feedback_failed",
                                   extra={"error": str(e), "code": code})
                    return None
                # Back off past the 60s quota window on throttling; shorter for transient errors
                cap = 65.0 if code == "ThrottlingException" else 30.0
                delay = min(1.0 * (2 ** attempt), cap) + random.uniform(0, 0.5)
                logger.info("bedrock_retry", extra={"attempt": attempt + 1,
                            "delay": round(delay, 1), "code": code})
                await asyncio.sleep(delay)

            except Exception as e:
                logger.warning("bedrock_feedback_failed", extra={"error": str(e)})
                return None

        return None

    def get_latest_analysis(self, arena_id: UUID, user_id: UUID) -> Optional[AnalysisResult]:
        """Get the latest analysis result for a participant."""
        key = (arena_id, user_id)
        session = self._sessions.get(key)
        return session.latest_result if session else None

    async def close_session(self, arena_id: UUID, user_id: UUID) -> Optional[AnalysisResult]:
        """
        Close and clean up a participant's audio analysis session.
        Returns the final analysis result.
        """
        key = (arena_id, user_id)
        session = self._sessions.pop(key, None)
        if not session:
            return None

        final_result = session.latest_result

        try:
            # Signal end of audio
            session.push_stream.close()

            # Stop recognition — call .get() so the C++ SDK thread fully shuts
            # down before we drop the reference (avoids segfaults/memory leaks).
            if session._recognizing:
                future = session.speech_recognizer.stop_continuous_recognition_async()
                await asyncio.get_event_loop().run_in_executor(None, future.get)
                session._recognizing = False

            logger.info(
                "audio_analysis_session_closed",
                extra={
                    "arena_id": str(arena_id),
                    "user_id": str(user_id),
                    "final_accuracy": final_result.accuracy_score,
                    "final_fluency": final_result.fluency_score,
                },
            )
        except Exception as e:
            logger.warning(
                "audio_analysis_session_close_error",
                extra={
                    "arena_id": str(arena_id),
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )

        return final_result

    async def close_all_sessions(self, arena_id: UUID) -> None:
        """Close all participant sessions for an arena (e.g. when session ends)."""
        keys_to_close = [
            (aid, uid) for (aid, uid) in self._sessions if aid == arena_id
        ]
        for aid, uid in keys_to_close:
            await self.close_session(aid, uid)

    def has_session(self, arena_id: UUID, user_id: UUID) -> bool:
        """Check if a participant has an active analysis session."""
        return (arena_id, user_id) in self._sessions


# Global singleton instance
audio_analysis_service = AudioAnalysisService()
