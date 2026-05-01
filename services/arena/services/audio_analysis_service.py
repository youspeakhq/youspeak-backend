"""
Real-time audio analysis service using Azure Speech Pronunciation Assessment.

Manages per-participant Azure Speech sessions during live arena sessions.
Feeds audio chunks into Azure's PushAudioInputStream for streaming pronunciation
assessment, collects incremental results, and generates LLM feedback summaries
via AWS Bedrock.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import azure.cognitiveservices.speech as speechsdk

from ..config import settings

logger = logging.getLogger(__name__)

# Azure Speech PCM format: 16kHz, 16-bit, mono
SAMPLE_RATE = 16000
BITS_PER_SAMPLE = 16
CHANNELS = 1

# Throttle settings
ANALYSIS_BROADCAST_INTERVAL_SECONDS = 5
FEEDBACK_SUMMARY_INTERVAL_SECONDS = 10

LANGUAGE_CODE_TO_AZURE_LOCALE = {
    "en": "en-US", "es": "es-ES", "fr": "fr-FR", "ru": "ru-RU",
    "ar": "ar-SA", "zh": "zh-CN", "pt": "pt-BR", "de": "de-DE",
    "it": "it-IT", "ja": "ja-JP", "ko": "ko-KR", "nl": "nl-NL",
    "pl": "pl-PL", "hi": "hi-IN", "vi": "vi-VN", "th": "th-TH",
    "sv": "sv-SE", "da": "da-DK", "fi": "fi-FI", "nb": "nb-NO",
    "ca": "ca-ES", "ms": "ms-MY", "ta": "ta-IN",
}


@dataclass
class WordResult:
    word: str
    accuracy_score: float
    error_type: str


@dataclass
class AnalysisResult:
    accuracy_score: float = 0.0
    fluency_score: float = 0.0
    pronunciation_score: float = 0.0
    prosody_score: Optional[float] = None
    words: List[WordResult] = field(default_factory=list)
    feedback_summary: Optional[str] = None
    language: str = "en-US"
    timestamp: float = 0.0


@dataclass
class ParticipantAudioSession:
    arena_id: UUID
    user_id: UUID
    language_locale: str
    push_stream: speechsdk.audio.PushAudioInputStream
    speech_recognizer: speechsdk.SpeechRecognizer
    latest_result: AnalysisResult = field(default_factory=AnalysisResult)
    last_broadcast_time: float = 0.0
    last_feedback_time: float = 0.0
    _recognizing: bool = False
    _recent_words: List[WordResult] = field(default_factory=list)
    _recent_accuracy_scores: List[float] = field(default_factory=list)
    _recent_fluency_scores: List[float] = field(default_factory=list)
    _recent_pronunciation_scores: List[float] = field(default_factory=list)


class AudioAnalysisService:
    def __init__(self):
        self._sessions: Dict[Tuple[UUID, UUID], ParticipantAudioSession] = {}
        self._broadcast_callback = None
        self._bedrock = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_broadcast_callback(self, callback):
        self._broadcast_callback = callback

    def _get_bedrock(self):
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
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def start_session(self, arena_id: UUID, user_id: UUID, language_code: str, student_name: str = "") -> bool:
        key = (arena_id, user_id)
        if key in self._sessions:
            return True

        if not settings.AZURE_SPEECH_KEY:
            logger.error("azure_speech_key_not_configured")
            return False

        locale = LANGUAGE_CODE_TO_AZURE_LOCALE.get(language_code, "en-US")

        try:
            speech_config = speechsdk.SpeechConfig(subscription=settings.AZURE_SPEECH_KEY, region=settings.AZURE_SPEECH_REGION)
            speech_config.speech_recognition_language = locale
            pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Word,
            )
            if locale == "en-US":
                pronunciation_config.enable_prosody_assessment()

            audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=SAMPLE_RATE, bits_per_sample=BITS_PER_SAMPLE, channels=CHANNELS)
            push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            pronunciation_config.apply_to(recognizer)

            session = ParticipantAudioSession(
                arena_id=arena_id, user_id=user_id, language_locale=locale,
                push_stream=push_stream, speech_recognizer=recognizer,
                latest_result=AnalysisResult(language=locale),
            )
            self._get_or_create_loop()
            recognizer.recognized.connect(lambda evt, s=session, name=student_name: self._on_recognized(evt, s, name))
            recognizer.canceled.connect(lambda evt, s=session: self._on_canceled(evt, s))
            recognizer.start_continuous_recognition_async()
            session._recognizing = True
            self._sessions[key] = session
            return True
        except Exception as e:
            logger.error(f"audio_analysis_session_start_failed: {e}")
            return False

    async def process_audio_chunk(self, arena_id: UUID, user_id: UUID, audio_data: bytes) -> None:
        key = (arena_id, user_id)
        session = self._sessions.get(key)
        if session:
            try:
                session.push_stream.write(audio_data)
            except Exception as e:
                logger.warning(f"audio_chunk_write_failed: {e}")

    def _on_recognized(self, evt: speechsdk.SpeechRecognitionEventArgs, session: ParticipantAudioSession, student_name: str):
        result = evt.result
        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return
        try:
            pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
            accuracy = pronunciation_result.accuracy_score or 0.0
            fluency = pronunciation_result.fluency_score or 0.0
            pronunciation = pronunciation_result.pronunciation_score or 0.0
            prosody = getattr(pronunciation_result, "prosody_score", None) if session.language_locale == "en-US" else None

            words = [WordResult(word=w.word, accuracy_score=w.accuracy_score or 0.0, error_type=w.error_type if hasattr(w, "error_type") else "None")
                     for w in (pronunciation_result.words or [])]

            session._recent_words.extend(words)
            session._recent_words = session._recent_words[-50:]
            session._recent_accuracy_scores.append(accuracy)
            session._recent_fluency_scores.append(fluency)
            session._recent_pronunciation_scores.append(pronunciation)
            session._recent_accuracy_scores = session._recent_accuracy_scores[-10:]
            session._recent_fluency_scores = session._recent_fluency_scores[-10:]
            session._recent_pronunciation_scores = session._recent_pronunciation_scores[-10:]

            avg_accuracy = sum(session._recent_accuracy_scores) / len(session._recent_accuracy_scores)
            avg_fluency = sum(session._recent_fluency_scores) / len(session._recent_fluency_scores)
            avg_pronunciation = sum(session._recent_pronunciation_scores) / len(session._recent_pronunciation_scores)

            session.latest_result = AnalysisResult(
                accuracy_score=round(avg_accuracy, 1),
                fluency_score=round(avg_fluency, 1),
                pronunciation_score=round(avg_pronunciation, 1),
                prosody_score=round(prosody, 1) if prosody is not None else None,
                words=list(session._recent_words[-10:]),
                language=session.language_locale,
                timestamp=time.time(),
            )

            now = time.time()
            if now - session.last_broadcast_time >= ANALYSIS_BROADCAST_INTERVAL_SECONDS:
                session.last_broadcast_time = now
                self._schedule_broadcast(session, student_name)
        except Exception as e:
            logger.error(f"pronunciation_result_processing_failed: {e}")

    def _on_canceled(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs, session: ParticipantAudioSession):
        logger.warning(f"speech_recognition_canceled: {evt.cancellation_details.reason}")

    def _schedule_broadcast(self, session: ParticipantAudioSession, student_name: str):
        if not self._broadcast_callback or not self._loop or self._loop.is_closed():
            return
        result = session.latest_result
        data = {
            "event_type": "ai_analysis",
            "data": {
                "user_id": str(session.user_id), "student_name": student_name,
                "accuracy_score": result.accuracy_score, "fluency_score": result.fluency_score,
                "prosody_score": result.prosody_score, "pronunciation_score": result.pronunciation_score,
                "words": [{"word": w.word, "accuracy": w.accuracy_score, "error_type": w.error_type} for w in result.words],
                "feedback_summary": result.feedback_summary, "language": result.language,
            },
        }
        now = time.time()
        should_generate_feedback = (now - session.last_feedback_time >= FEEDBACK_SUMMARY_INTERVAL_SECONDS and len(session._recent_words) >= 3)
        coro = self._generate_and_broadcast(session, data, student_name) if should_generate_feedback else self._broadcast_callback(session.arena_id, data)
        if should_generate_feedback:
            session.last_feedback_time = now
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _generate_and_broadcast(self, session: ParticipantAudioSession, data: dict, student_name: str):
        try:
            feedback = await self._generate_feedback_summary(session)
            if feedback:
                session.latest_result.feedback_summary = feedback
                data["data"]["feedback_summary"] = feedback
        except Exception as e:
            logger.warning(f"feedback_generation_failed: {e}")
        if self._broadcast_callback:
            await self._broadcast_callback(session.arena_id, data)

    async def _generate_feedback_summary(self, session: ParticipantAudioSession) -> Optional[str]:
        words = session._recent_words[-15:]
        if not words: return None
        problem_words = [w for w in words if w.accuracy_score < 70]
        if not problem_words and session.latest_result.accuracy_score > 85:
            return "Great pronunciation! Keep up the natural flow."
        word_details = ", ".join(f'"{w.word}" ({w.accuracy_score:.0f}%)' for w in words[-10:])
        prompt = (f"You are a language pronunciation coach. A student is speaking {session.language_locale}. "
                  f"Their recent word scores: {word_details}. Overall accuracy: {session.latest_result.accuracy_score:.0f}%, "
                  f"fluency: {session.latest_result.fluency_score:.0f}%. Give ONE concise sentence of coaching feedback (max 20 words).")
        try:
            bedrock = self._get_bedrock()
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: bedrock.converse(
                modelId=settings.BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 60, "temperature": 0.3},
            ))
            return response["output"]["message"]["content"][0]["text"].strip()[:200]
        except Exception: return None

    async def close_session(self, arena_id: UUID, user_id: UUID) -> Optional[AnalysisResult]:
        key = (arena_id, user_id)
        session = self._sessions.pop(key, None)
        if not session: return None
        final_result = session.latest_result
        try:
            session.push_stream.close()
            if session._recognizing:
                session.speech_recognizer.stop_continuous_recognition_async()
            logger.info(f"audio_analysis_session_closed: {arena_id}, {user_id}")
        except Exception as e:
            logger.warning(f"audio_analysis_session_close_error: {e}")
        return final_result

    async def close_all_sessions(self, arena_id: UUID) -> None:
        keys_to_close = [k for k in self._sessions if k[0] == arena_id]
        for aid, uid in keys_to_close:
            await self.close_session(aid, uid)

audio_analysis_service = AudioAnalysisService()
