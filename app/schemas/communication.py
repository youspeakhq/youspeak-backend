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

    @field_validator('start_time')
    @classmethod
    def normalize_start_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Strip timezone info from start_time to match DB TIMESTAMP WITHOUT TIME ZONE."""
        if v is not None and v.tzinfo is not None:
            # Convert to UTC and strip timezone
            return v.replace(tzinfo=None)
        return v


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

    @field_validator('start_time')
    @classmethod
    def normalize_start_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Strip timezone info from start_time to match DB TIMESTAMP WITHOUT TIME ZONE."""
        if v is not None and v.tzinfo is not None:
            return v.replace(tzinfo=None)
        return v


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


# --- Phase 5: Challenge Pool ---


class ChallengePoolListItem(BaseModel):
    """Challenge pool item for browsing"""
    id: UUID
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    arena_mode: Optional[str] = None
    judging_mode: Optional[str] = None
    criteria: List[Dict[str, object]] = []  # [{name, weight_percentage}]
    rules: List[str] = []
    usage_count: int = 0
    published_at: datetime
    published_by_name: Optional[str] = None


class ChallengePoolResponse(BaseModel):
    """Response for GET /arenas/pool"""
    challenges: List[ChallengePoolListItem]
    total: int
    page: int
    page_size: int


class ChallengePoolDetailResponse(BaseModel):
    """Detailed challenge pool item"""
    id: UUID
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    arena_mode: Optional[str] = None
    judging_mode: Optional[str] = None
    ai_co_judge_enabled: bool = False
    team_size: Optional[int] = None
    criteria: List[Dict[str, object]] = []
    rules: List[str] = []
    usage_count: int = 0
    published_at: datetime
    published_by_name: Optional[str] = None


class PublishToChallengePoolRequest(BaseModel):
    """Request for POST /arenas/{id}/publish-to-pool"""
    pass  # Empty body


class PublishToChallengePoolResponse(BaseModel):
    """Response for publishing to challenge pool"""
    success: bool
    arena_id: UUID
    published_at: datetime
    message: str


class CloneChallengeRequest(BaseModel):
    """Request for POST /arenas/pool/{id}/clone"""
    class_id: UUID
    customize_title: Optional[str] = None


class CloneChallengeResponse(BaseModel):
    """Response for cloning challenge"""
    success: bool
    new_arena_id: UUID
    source_arena_id: UUID
    message: str


# --- Phase 6: Collaborative Mode Teams ---


class TeamMemberInfo(BaseModel):
    """Team member information"""
    student_id: UUID
    student_name: str
    role: str  # 'leader' | 'member'
    avatar_url: Optional[str] = None


class TeamInfo(BaseModel):
    """Team information"""
    team_id: UUID
    team_name: str
    members: List[TeamMemberInfo] = []
    created_at: datetime


class CreateTeamRequest(BaseModel):
    """Request for POST /arenas/{id}/teams"""
    team_name: str
    student_ids: List[UUID]
    leader_id: Optional[UUID] = None  # If provided, this student becomes team leader


class CreateTeamResponse(BaseModel):
    """Response for creating a team"""
    success: bool
    team: TeamInfo
    message: str


class BatchCreateTeamRequest(BaseModel):
    """Request for POST /arenas/{id}/teams/batch"""
    teams: List[CreateTeamRequest]


class BatchCreateTeamResponse(BaseModel):
    """Response for batch creating teams"""
    success: bool
    created_teams: List[TeamInfo]
    message: str


class ListTeamsResponse(BaseModel):
    """Response for GET /arenas/{id}/teams"""
    arena_id: UUID
    arena_mode: str
    teams: List[TeamInfo] = []
    total_teams: int
    total_students: int


class ArenaHistoryItem(BaseModel):
    """Historical arena entry"""
    id: UUID
    title: str
    class_name: str
    status: ArenaStatus
    session_state: str
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    arena_mode: Optional[str] = None
    participant_count: int
    published_at: Optional[datetime] = None


class ArenaHistoryResponse(BaseModel):
    """Response for GET /arenas/history"""
    arenas: List[ArenaHistoryItem]
    total: int
    page: int
    page_size: int


# --- Announcement ---


# --- Announcement ---


class AnnouncementCreate(BaseModel):
    class_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    type: AnnouncementType
    message: str
    send_notification: bool = False  # If true, triggers immediate notification


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    type: Optional[AnnouncementType] = None


class AnnouncementResponse(BaseModel):
    id: UUID
    author_id: UUID
    class_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    type: AnnouncementType
    message: str
    created_at: datetime
    author_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AnnouncementListResponse(BaseModel):
    announcements: List[AnnouncementResponse]
    total: int
