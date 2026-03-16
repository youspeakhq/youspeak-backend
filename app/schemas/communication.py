from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime

from app.models.enums import ArenaStatus, AnnouncementType

# --- Arena ---


class ArenaCreate(BaseModel):
    class_id: UUID
    title: str
    description: Optional[str] = None
    rules: List[str] = []
    criteria: Dict[str, int]  # name -> weight_percentage
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaSchedule(BaseModel):
    start_time: datetime
    duration_min: int


class ArenaUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ArenaStatus] = None
    rules: Optional[List[str]] = None
    criteria: Optional[Dict[str, int]] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaListRow(BaseModel):
    id: UUID
    title: str
    status: ArenaStatus
    class_id: UUID
    class_name: Optional[str] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    description: Optional[str] = None
    status: ArenaStatus
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    criteria: List[Dict[str, object]]  # [{"name": str, "weight_percentage": int}]
    rules: List[str]

    model_config = ConfigDict(from_attributes=True)


# --- Phase 1: Arena Session Configuration ---


class StudentListItem(BaseModel):
    """Student information for selection UI"""
    id: UUID
    name: str
    avatar_url: Optional[str] = None
    status: Optional[str] = "active"

    model_config = ConfigDict(from_attributes=True)


class ArenaSessionConfig(BaseModel):
    """Configuration for initializing an arena session"""
    arena_mode: Literal["competitive", "collaborative"]
    judging_mode: Literal["teacher_only", "hybrid"]
    ai_co_judge_enabled: bool = False
    student_selection_mode: Literal["manual", "hybrid", "randomize"]
    selected_student_ids: List[UUID] = []
    team_size: Optional[int] = None

    @field_validator('team_size')
    @classmethod
    def validate_team_size(cls, v, info):
        arena_mode = info.data.get('arena_mode')
        if arena_mode == 'collaborative' and v is None:
            raise ValueError('team_size is required for collaborative mode')
        if v is not None and (v < 2 or v > 5):
            raise ValueError('team_size must be between 2 and 5')
        return v

    @field_validator('selected_student_ids')
    @classmethod
    def validate_selected_students(cls, v, info):
        selection_mode = info.data.get('student_selection_mode')
        if selection_mode == 'manual' and len(v) == 0:
            raise ValueError('selected_student_ids required for manual selection mode')
        return v


class ArenaInitializeRequest(ArenaSessionConfig):
    """Request body for POST /arenas/{id}/initialize"""
    pass


class ArenaInitializeResponse(BaseModel):
    """Response for arena initialization"""
    session_id: UUID  # Same as arena_id
    status: Literal["initialized"]
    participants: List[StudentListItem]
    configuration: ArenaSessionConfig


class StudentSearchResponse(BaseModel):
    """Response for GET /students/search"""
    students: List[StudentListItem]
    total: int
    page: int
    page_size: int


class RandomizeStudentsRequest(BaseModel):
    """Request for POST /arenas/{id}/students/randomize"""
    class_id: UUID
    participant_count: int


class RandomizeStudentsResponse(BaseModel):
    """Response for randomize endpoint"""
    selected_students: List[StudentListItem]


class HybridSelectionRequest(BaseModel):
    """Request for POST /arenas/{id}/students/hybrid"""
    manual_selections: List[UUID]
    randomize_count: int
    class_id: UUID


class HybridSelectionResponse(BaseModel):
    """Response for hybrid selection endpoint"""
    final_participants: List[StudentListItem]


# --- Phase 2: Waiting Room & Admission ---


class JoinCodeGenerateResponse(BaseModel):
    """Response for POST /arenas/{id}/join-code"""
    join_code: str  # 6-digit alphanumeric
    qr_code_url: str  # URL to QR code image
    expires_at: datetime


class WaitingRoomJoinRequest(BaseModel):
    """Request for POST /arenas/{id}/waiting-room/join"""
    join_code: str


class WaitingRoomJoinResponse(BaseModel):
    """Response for student joining waiting room"""
    waiting_room_id: UUID
    status: Literal["pending"]
    position_in_queue: int


class WaitingRoomEntry(BaseModel):
    """Waiting room entry information"""
    entry_id: UUID
    student_id: UUID
    student_name: str
    avatar_url: Optional[str] = None
    entry_timestamp: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class WaitingRoomListResponse(BaseModel):
    """Response for GET /arenas/{id}/waiting-room"""
    pending_students: List[WaitingRoomEntry]
    total_pending: int
    total_admitted: int
    total_rejected: int


class WaitingRoomAdmitResponse(BaseModel):
    """Response for admit/reject actions"""
    success: bool
    participant_id: Optional[UUID] = None  # Only for admit


class WaitingRoomRejectRequest(BaseModel):
    """Request for POST /arenas/{id}/waiting-room/{entry_id}/reject"""
    reason: Optional[str] = None


# --- Phase 3: WebSocket & Live Sessions ---


class ArenaSessionStateResponse(BaseModel):
    """Response for GET /arenas/{id}/session - Current session state"""
    arena_id: UUID
    session_state: str  # initialized, live, completed, cancelled
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    active_speaker_id: Optional[UUID] = None
    participants: List[Dict] = []  # List of participant info


class ArenaSessionStartRequest(BaseModel):
    """Request for POST /arenas/{id}/start"""
    pass  # Empty body - just triggers session start


class ArenaSessionEndRequest(BaseModel):
    """Request for POST /arenas/{id}/end"""
    reason: Optional[str] = None  # Optional reason for ending early


# WebSocket event schemas

class WSClientEvent(BaseModel):
    """Base schema for client→server WebSocket events"""
    event_type: Literal[
        "speaking_started",
        "speaking_stopped",
        "reaction_sent",
        "audio_muted",
        "audio_unmuted"
    ]
    timestamp: Optional[datetime] = None


class WSSpeakingEvent(WSClientEvent):
    """Client sends when starting/stopping speaking"""
    event_type: Literal["speaking_started", "speaking_stopped"]


class WSReactionEvent(WSClientEvent):
    """Client sends a reaction (emoji, etc.)"""
    event_type: Literal["reaction_sent"]
    reaction_type: str  # "thumbs_up", "clap", etc.


class WSAudioEvent(WSClientEvent):
    """Client mutes/unmutes audio"""
    event_type: Literal["audio_muted", "audio_unmuted"]


class WSServerEvent(BaseModel):
    """Base schema for server→client WebSocket broadcasts"""
    event_type: Literal[
        "session_state",
        "speaking_update",
        "engagement_update",
        "reaction_broadcast",
        "participant_joined",
        "participant_left",
        "session_ended"
    ]
    timestamp: datetime
    data: Dict  # Event-specific payload


# --- Phase 4: Evaluation & Publishing ---


class ParticipantScoreCard(BaseModel):
    """Individual participant scoring data"""
    participant_id: UUID
    student_id: UUID
    student_name: str
    avatar_url: Optional[str] = None
    total_speaking_duration_seconds: int
    engagement_score: float  # 0.00 to 100.00
    reactions_received: int
    ai_pronunciation_score: Optional[float] = None
    ai_fluency_score: Optional[float] = None
    teacher_rating: Optional[float] = None


class ArenaScoresResponse(BaseModel):
    """Response for GET /arenas/{id}/scores - Live scoring data"""
    arena_id: UUID
    session_state: str
    participants: List[ParticipantScoreCard]
    top_performers: List[UUID]  # Ranked by engagement_score


class ParticipantAnalytics(BaseModel):
    """Detailed analytics for a single participant"""
    participant_id: UUID
    student_id: UUID
    speaking_timeline: List[Dict]  # [{start_time, end_time, duration_seconds}]
    engagement_timeline: List[Dict]  # [{timestamp, score}]
    reactions_timeline: List[Dict]  # [{timestamp, reaction_type, from_user_id}]
    total_speaking_time_seconds: int
    average_engagement_score: float
    peak_engagement_score: float
    total_reactions_received: int
    reaction_breakdown: Dict[str, int]  # reaction_type -> count


class ArenaAnalyticsResponse(BaseModel):
    """Response for GET /arenas/{id}/analytics - Detailed analytics"""
    arena_id: UUID
    session_duration_minutes: Optional[int] = None
    total_participants: int
    participants: List[ParticipantAnalytics]
    aggregate_stats: Dict  # Overall session statistics


class TeacherRatingRequest(BaseModel):
    """Request for POST /arenas/{id}/participants/{participant_id}/rate"""
    criteria_scores: Dict[str, float]  # criterion_name -> score (0-100)
    overall_rating: float  # 0-100
    feedback: Optional[str] = None


class TeacherRatingResponse(BaseModel):
    """Response for teacher rating submission"""
    success: bool
    participant_id: UUID
    overall_rating: float


class PublishArenaRequest(BaseModel):
    """Request for POST /arenas/{id}/publish"""
    include_ai_analysis: bool = True
    visibility: Literal["class", "school", "public"] = "class"


class PublishArenaResponse(BaseModel):
    """Response for publishing arena results"""
    success: bool
    arena_id: UUID
    published_at: datetime
    share_url: Optional[str] = None


# --- Announcement ---


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    class_ids: List[UUID] = []
    attachments: List[str] = []  # URLs
    is_reminder: bool = False
    reminder_date: Optional[datetime] = None


class AnnouncementResponse(BaseModel):
    id: UUID
    type: AnnouncementType
    message: str
    created_at: datetime
    author_name: str

    model_config = ConfigDict(from_attributes=True)
