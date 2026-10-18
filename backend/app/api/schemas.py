"""公开 API 响应模型（OpenAPI 契约真源）。

- 路由直返 JSONResponse，response_model 仅用于生成 OpenAPI 文档（零运行时行为）；
- 字段口径与实际响应对齐，可空性按真实行为声明；
- 前端经 openapi-typescript 从 /openapi.json 生成 TS 类型，CI 比对漂移。
"""
from __future__ import annotations

from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "ok"
    data: T
    requestId: Optional[str] = None
    nextStep: Optional[str] = None


# ------------------------------ 通用与 context ------------------------------

class HealthData(BaseModel):
    status: str
    service: str
    env: str


class CalibrationInfo(BaseModel):
    status: Literal["none", "personal"]


class MeContext(BaseModel):
    authenticated: bool
    accountId: Optional[str] = None
    username: Optional[str] = None
    dialectBackground: Optional[str] = None
    calibration: CalibrationInfo
    nextLevelId: Optional[str] = None


# --------------------------------- 关卡 -------------------------------------

class CompletionKeys(BaseModel):
    quizIds: List[str]
    practiceStepIds: List[str]


class LevelSummary(BaseModel):
    id: str
    order: int
    layer: Literal["vowel", "initial", "syllable"]
    type: str
    targetSound: str
    pinyin: str
    representativeChar: Optional[str] = None
    title: str
    oneLiner: str
    demoMediaId: Optional[str] = None
    availability: Literal["open", "closed"]
    completionKeys: CompletionKeys


class LevelSkeleton(BaseModel):
    id: str
    order: int
    layer: Literal["vowel", "initial", "syllable"]
    targetSound: str
    availability: Literal["closed"]


class ConfusablePair(BaseModel):
    a: str
    b: str


class LevelsResponse(BaseModel):
    levels: List[LevelSummary]
    # 未开放但 skeleton_public 的关卡骨架；空列表时后端可能省略这两个键
    skeleton: List[LevelSkeleton] = []
    confusablePairs: List[ConfusablePair] = []


class LevelNav(BaseModel):
    prev: Optional[str] = None
    next: Optional[str] = None
    confusables: Optional[List[str]] = None


class ArticulationMedia(BaseModel):
    mediaId: str
    kind: Literal["image", "animation", "video"]
    altText: str


class SagittalLips(BaseModel):
    aperture: float
    rounding: float
    contact: Literal["none", "bilabial", "labiodental"]


class SagittalTongueTip(BaseModel):
    place: Literal["rest", "dental", "alveolar", "postalveolar", "retroflex"]
    stricture: Literal["open", "approximant", "fricative", "closure"]


class SagittalTongueBody(BaseModel):
    height: float
    backness: float
    stricture: Literal["open", "approximant", "fricative", "closure"]


class SagittalKeyframe(BaseModel):
    label: str
    holdMs: int
    jaw: float
    lips: SagittalLips
    tongueTip: SagittalTongueTip
    tongueBody: SagittalTongueBody
    velum: Literal["raised", "lowered"]
    airflow: Literal["none", "oral", "nasal", "burst", "aspirated_burst",
                     "friction", "affricate"]
    voicing: bool


class ArticulationSagittal(BaseModel):
    keyframes: List[SagittalKeyframe]


class Articulation(BaseModel):
    media: Optional[List[ArticulationMedia]] = None
    description: str
    sagittal: Optional[ArticulationSagittal] = None
    model3dMediaId: Optional[str] = None


class DemoItem(BaseModel):
    mediaId: str
    speed: Literal["normal", "slow"]
    voice: Optional[str] = None


class QuizOption(BaseModel):
    text: str
    mediaId: Optional[str] = None


class QuizQuestion(BaseModel):
    id: str
    stimulusMediaId: str
    prompt: str
    options: List[QuizOption]
    answerIndex: int
    explanation: Optional[str] = None


class PracticeStep(BaseModel):
    id: str
    title: str
    instruction: str
    repeat: Optional[int] = None
    durationSec: Optional[float] = None
    bodyCue: str
    mediaId: Optional[str] = None


class Misconception(BaseModel):
    phenomenon: str
    fix: str


class Professional(BaseModel):
    description: str


class DetectionTask(BaseModel):
    promptText: str
    sampleMediaId: Optional[str] = None
    allowedMetrics: List[str]
    available: bool


class LevelDetail(BaseModel):
    id: str
    order: int
    layer: Literal["vowel", "initial", "syllable"]
    type: str
    targetSound: str
    pinyin: str
    representativeChar: Optional[str] = None
    title: str
    oneLiner: str
    goal: str
    applicableIssues: Optional[str] = None
    tags: Optional[List[str]] = None
    nav: Optional[LevelNav] = None
    articulation: Optional[Articulation] = None
    demos: Optional[List[DemoItem]] = None
    quizzes: Optional[List[QuizQuestion]] = None
    practice: Optional[List[PracticeStep]] = None
    misconceptions: Optional[List[Misconception]] = None
    professional: Optional[Professional] = None
    detection: Optional[DetectionTask] = None


# --------------------------------- 搜索 -------------------------------------

class SearchResponse(BaseModel):
    results: List[LevelSummary]
    near: List[LevelSummary] = []
    query: Optional[str] = None


# --------------------------------- 文章 -------------------------------------

class ArticleCategory(BaseModel):
    id: int
    name: str


class ArticleCategoriesResponse(BaseModel):
    categories: List[ArticleCategory]


class ArticleSummary(BaseModel):
    slug: str
    title: str
    category: str
    summary: Optional[str] = None
    demoMediaId: Optional[str] = None
    relatedLevelIds: Optional[List[str]] = None


class ArticlesResponse(BaseModel):
    articles: List[ArticleSummary]


class ArticleReference(BaseModel):
    title: str
    source: str
    license: str


class ArticlePracticeItem(BaseModel):
    title: str
    instruction: str


class RelatedLevel(BaseModel):
    levelId: str
    available: bool


class ArticleDemo(BaseModel):
    mediaId: str
    text: Optional[str] = None


class ArticleDetail(BaseModel):
    slug: str
    title: str
    category: str
    summary: Optional[str] = None
    markdown: str
    demo: Optional[ArticleDemo] = None
    practice: Optional[List[ArticlePracticeItem]] = None
    references: Optional[List[ArticleReference]] = None
    relatedLevels: Optional[List[RelatedLevel]] = None


# ------------------------------ 音频与标定 ----------------------------------

class AudioUploadResponse(BaseModel):
    audioId: str
    duration: float
    format: str


class F0Frame(BaseModel):
    t: float
    hz: Optional[float] = None


class F0Response(BaseModel):
    algorithmVersion: str
    hopMs: int
    frames: List[F0Frame]
    voicedRanges: Optional[List[List[float]]] = None
    voicedRatio: Optional[float] = None


class FormantFrame(BaseModel):
    t: float
    f1: Optional[float] = None
    f2: Optional[float] = None


class FormantsResponse(BaseModel):
    algorithmVersion: str
    frames: Optional[List[FormantFrame]] = None
    vowelSegments: Optional[List[List[float]]] = None  # 每段 [start, end] 秒


class PitchRange(BaseModel):
    fLo: float
    fHi: float


class PitchCalibrationInfo(BaseModel):
    text: str
    textVersion: str
    status: Literal["none", "personal"]
    pitchRange: Optional[PitchRange] = None
    vowelSpaceReady: Optional[bool] = None
    updatedAt: Optional[str] = None


class CalibrationOkResult(BaseModel):
    ok: bool
    status: Literal["personal"]
    pitchRange: PitchRange
    vowelSpaceReady: bool
    rangeSnapshotId: Optional[str] = None
    updatedAt: Optional[str] = None


class CalibrationSignalCheckAdvice(BaseModel):
    advice: Optional[str] = None


class CalibrationFailSignal(BaseModel):
    verdict: Optional[Literal["fail"]] = None
    volume: Optional[CalibrationSignalCheckAdvice] = None
    noise: Optional[CalibrationSignalCheckAdvice] = None
    clipping: Optional[CalibrationSignalCheckAdvice] = None
    duration: Optional[CalibrationSignalCheckAdvice] = None


class CalibrationFailResult(BaseModel):
    reason: str
    signal: Optional[CalibrationFailSignal] = None


# ------------------------------- 录音与结果 ---------------------------------

class RecordingError(BaseModel):
    code: str
    retryable: bool


class RecordingDTO(BaseModel):
    recordingId: str
    audioId: str
    levelId: str
    status: Literal["processing", "completed", "failed"]
    stage: Optional[Literal["queued", "analyzing", "scoring", "finalizing"]] = None
    error: Optional[RecordingError] = None
    createdAt: Optional[str] = None


class VolumeCheck(BaseModel):
    dbfs: Optional[float] = None
    pass_: Optional[bool] = Field(None, alias="pass")
    advice: Optional[str] = None


class NoiseCheck(BaseModel):
    snrDb: Optional[float] = None
    pass_: Optional[bool] = Field(None, alias="pass")
    advice: Optional[str] = None


class ClippingCheck(BaseModel):
    ratio: Optional[float] = None
    pass_: Optional[bool] = Field(None, alias="pass")
    advice: Optional[str] = None


class DurationCheck(BaseModel):
    valueSec: Optional[float] = None
    expectedSec: Optional[float] = None
    pass_: Optional[bool] = Field(None, alias="pass")
    advice: Optional[str] = None


class QualitySignal(BaseModel):
    verdict: Optional[Literal["pass", "fail"]] = None
    volume: Optional[VolumeCheck] = None
    noise: Optional[NoiseCheck] = None
    clipping: Optional[ClippingCheck] = None
    duration: Optional[DurationCheck] = None


class QualityReading(BaseModel):
    missing: Optional[List[str]] = None
    extra: Optional[List[str]] = None
    repeated: Optional[List[str]] = None
    replaced: Optional[List[str]] = None
    disordered: Optional[bool] = None
    advice: Optional[str] = None


class Quality(BaseModel):
    """录音质量提示（FR-1301）：仅作辅助提示，不拦截评分与可视化。"""
    signal: Optional[QualitySignal] = None
    reading: Optional[QualityReading] = None
    advice: Optional[str] = None


class PhenomenonPosition(BaseModel):
    syllableIndex: Optional[int] = None
    part: str


class Phenomenon(BaseModel):
    tag: str
    syllable: Optional[str] = None
    position: Optional[PhenomenonPosition] = None
    description: str


class FourStepPractice(BaseModel):
    levelId: Optional[str] = None
    stepRef: str


class FourStep(BaseModel):
    phenomenon: str
    possibleCause: str
    cue: str
    practice: FourStepPractice
    wordingSource: str


class CurvePoint(BaseModel):
    t: float
    v: float


class CurveSegment(BaseModel):
    syllable: Optional[str] = None
    toneValue: Optional[float] = None
    user: Optional[List[CurvePoint]] = None
    reference: Optional[List[CurvePoint]] = None


class ResultCurve(BaseModel):
    status: Literal["ok", "not_available"]
    scale: Optional[str] = None
    segments: Optional[List[CurveSegment]] = None
    rangeSnapshotId: Optional[str] = None
    note: Optional[str] = None


class FormantRaw(BaseModel):
    f1Mean: Optional[float] = None
    f2Mean: Optional[float] = None


class FormantUser(BaseModel):
    f1: Optional[float] = None
    f2: Optional[float] = None
    raw: Optional[FormantRaw] = None


class FormantRegion(BaseModel):
    center: Optional[List[float]] = None
    radius: Optional[float] = None
    vowel: Optional[str] = None


class ResultFormants(BaseModel):
    status: Literal["ok", "not_available"]
    space: Optional[str] = None
    user: Optional[FormantUser] = None
    referenceRegion: Optional[FormantRegion] = None
    deviation: Optional[float] = None
    note: Optional[str] = None


class VotSpan(BaseModel):
    """单侧送气段时段：清辅音起始 → 嗓音起始（FR-1005）。"""
    onsetSec: float                    # 爆破/摩擦噪声起点（秒）
    voicingOnsetSec: float             # 嗓音起始（秒）
    votMs: float                       # VOT = 嗓音起始 − 清辅音起始（毫秒）


class ResultVot(BaseModel):
    status: Literal["ok", "not_available"]
    targetSound: Optional[str] = None
    aspiration: Optional[Literal["aspirated", "unaspirated", "fricative", "voiced"]] = None
    user: Optional[VotSpan] = None
    reference: Optional[VotSpan] = None
    referenceMediaId: Optional[str] = None   # 参考示范音频（前端拉取波形用）
    note: Optional[str] = None


class AssessmentResult(BaseModel):
    levelId: str
    providerVersion: str
    algorithmVersion: str
    quality: Quality
    score: Optional[float] = None
    phenomena: Optional[List[Phenomenon]] = None
    fourSteps: Optional[List[FourStep]] = None
    curve: Optional[ResultCurve] = None
    formants: Optional[ResultFormants] = None
    vot: Optional[ResultVot] = None


class RecordingWithResult(BaseModel):
    recording: RecordingDTO
    result: Optional[AssessmentResult] = None


class RecordingDeleted(BaseModel):
    deleted: bool
    alreadyDeleted: Optional[bool] = None


class RecordingOnly(BaseModel):
    """202 PROCESSING 响应负载。"""
    recording: RecordingDTO


class ClearArchiveResponse(BaseModel):
    deleted: int


# ------------------------------ 档案与学习 ----------------------------------

class ArchiveRecordingSummary(BaseModel):
    recordingId: str
    audioId: str
    levelId: str
    createdAt: Optional[str] = None
    verdict: Optional[str] = None
    qualityAdvice: Optional[str] = None
    score: Optional[float] = None


class ArchiveListResponse(BaseModel):
    recordings: Optional[List[ArchiveRecordingSummary]] = None
    nextCursor: Optional[str] = None


class ArchiveCompareSide(BaseModel):
    recording: ArchiveRecordingSummary
    result: Optional[AssessmentResult] = None
    rangeSnapshot: Optional[dict] = None


class CompareDimensions(BaseModel):
    score: bool = False
    curve: bool = False


class CompareDifference(BaseModel):
    dimension: str
    description: str


class ArchiveCompareResponse(BaseModel):
    a: ArchiveCompareSide
    b: ArchiveCompareSide
    comparable: CompareDimensions
    reasons: Optional[List[str]] = None
    differences: Optional[List[CompareDifference]] = None


class LearningEventsResponse(BaseModel):
    accepted: int
    duplicates: int
    rejected: Optional[List[dict]] = None


class ProgressQuiz(BaseModel):
    passed: int
    total: int


class ProgressPractice(BaseModel):
    done: int
    total: int


class ProgressLevel(BaseModel):
    levelId: str
    completed: bool
    quiz: ProgressQuiz
    practice: ProgressPractice


class MeProgress(BaseModel):
    levels: List[ProgressLevel]
    nextLevelId: Optional[str] = None


# -------------------------------- 账号 --------------------------------------

class RegisterResponse(BaseModel):
    accountId: str
    username: str
    dialectBackground: Optional[str] = None


class ProfileResponse(BaseModel):
    """PATCH /api/me/profile 响应：方言区/母语背景设置结果"""
    accountId: str
    username: str
    dialectBackground: Optional[str] = None


class LoginContextPartial(BaseModel):
    """login 响应只带部分身份字段；全量以 GET /api/me/context 为准。"""
    authenticated: bool
    accountId: Optional[str] = None
    username: Optional[str] = None


class AuthLoginResponse(BaseModel):
    context: LoginContextPartial


class LoggedOutResponse(BaseModel):
    loggedOut: bool


class DeletedResponse(BaseModel):
    deleted: bool


# -------------------------------- 反馈 --------------------------------------

class FeedbackResponse(BaseModel):
    feedbackId: str


class WishResponse(BaseModel):
    wishId: str
