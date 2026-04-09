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
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
        # Bedrock client (lazy init)
        self._bedrock = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_broadcast_callback(self, callback):
        """Set the async callback for broadcasting analysis results.

        Signature: async def callback(arena_id: UUID, data: dict) -> None
        """
        self._broadcast_callback = callback

    def _get_bedrock(self):
        """Lazy-init Bedrock client (reuse boto3 pattern from curriculum service)."""
        if self._bedrock is None:
            import boto3
            from botocore.config import Config

            config = Config(
                region_name=settings.AWS_REGION,
                retries={"max_attempts": 2},
                connect_timeout=5,
                read_timeout=15,
            )
            self._bedrock = boto3.client("bedrock-runtime", config=config)
        return self._bedrock

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop, caching it for use from SDK callback threads."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_event_loop()
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
                granularity=speechsdk.PronunciationAssessmentGranularity.Word,
            )
            # Enable prosody for en-US (only supported locale)
            if locale == "en-US":
                pronunciation_config.enable_prosody_assessment()

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
            pronunciation_result = speechsdk.PronunciationAssessmentResult(result)

            accuracy = pronunciation_result.accuracy_score or 0.0
            fluency = pronunciation_result.fluency_score or 0.0
            pronunciation = pronunciation_result.pronunciation_score or 0.0
            prosody = None
            if session.language_locale == "en-US":
                prosody = getattr(pronunciation_result, "prosody_score", None)

            # Extract word-level results
            words = []
            if pronunciation_result.words:
                for w in pronunciation_result.words:
                    words.append(WordResult(
                        word=w.word,
                        accuracy_score=w.accuracy_score or 0.0,
                        error_type=w.error_type if hasattr(w, "error_type") else "None",
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

            session.latest_result = AnalysisResult(
                accuracy_score=round(avg_accuracy, 1),
                fluency_score=round(avg_fluency, 1),
                pronunciation_score=round(avg_pronunciation, 1),
                prosody_score=round(prosody, 1) if prosody is not None else None,
                words=list(session._recent_words[-10:]),  # Last 10 words for broadcast
                language=session.language_locale,
                timestamp=time.time(),
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
        """Schedule an async broadcast from the SDK callback thread."""
        if not self._broadcast_callback or not self._loop:
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

        if should_generate_feedback:
            session.last_feedback_time = now
            # Generate feedback then broadcast
            asyncio.run_coroutine_threadsafe(
                self._generate_and_broadcast(session, data, student_name),
                self._loop,
            )
        else:
            # Broadcast immediately without new feedback
            asyncio.run_coroutine_threadsafe(
                self._broadcast_callback(session.arena_id, data),
                self._loop,
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

    async def _generate_feedback_summary(self, session: ParticipantAudioSession) -> Optional[str]:
        """
        Generate a 1-sentence coaching tip using Bedrock (Nova Lite).
        Based on recent word-level pronunciation scores.
        """
        words = session._recent_words[-15:]
        if not words:
            return None

        # Find mispronounced words
        problem_words = [w for w in words if w.accuracy_score < 70]
        if not problem_words and session.latest_result.accuracy_score > 85:
            return "Great pronunciation! Keep up the natural flow."

        word_details = ", ".join(
            f'"{w.word}" ({w.accuracy_score:.0f}%)' for w in words[-10:]
        )
        problem_detail = ""
        if problem_words:
            problem_detail = f" Mispronounced: {', '.join(w.word for w in problem_words[:3])}."

        prompt = (
            f"You are a language pronunciation coach. A student is speaking {session.language_locale}. "
            f"Their recent word scores: {word_details}.{problem_detail} "
            f"Overall accuracy: {session.latest_result.accuracy_score:.0f}%, "
            f"fluency: {session.latest_result.fluency_score:.0f}%. "
            f"Give ONE concise sentence of coaching feedback (max 20 words). "
            f"Focus on the most impactful improvement."
        )

        try:
            bedrock = self._get_bedrock()
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: bedrock.converse(
                    modelId=settings.BEDROCK_MODEL_ID,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 60, "temperature": 0.3},
                ),
            )
            text = response["output"]["message"]["content"][0]["text"].strip()
            # Truncate if somehow too long
            if len(text) > 200:
                text = text[:197] + "..."
            return text
        except Exception as e:
            logger.warning("bedrock_feedback_failed", extra={"error": str(e)})
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

            # Stop recognition
            if session._recognizing:
                session.speech_recognizer.stop_continuous_recognition_async()
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
