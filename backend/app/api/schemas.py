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
    gender: Optional[str] = None
    calibration: CalibrationInfo
    nextLevelId: Optional[str] = None


# --------------------------------- 关卡 -------------------------------------

class LevelSummary(BaseModel):
    id: str
    order: int
    layer: Literal["vowel", "initial", "syllable"]
    type: str
    targetSound: str
    pinyin: str
    representativeChar: Optional[str] = None
    title: str
    phonology: Optional["LevelPhonology"] = None
    demoMediaId: Optional[str] = None
    availability: Literal["open", "closed"]


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
    # 交互动画由前端内置组件渲染（如 ma-sagittal 正中矢状面动画）；
    # 缺省时按静态图/视频直出。媒体资产本身仍是该动画的规范存档。
    component: Optional[str] = None


class Articulation(BaseModel):
    media: Optional[List[ArticulationMedia]] = None
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


class Professional(BaseModel):
    description: str


class LevelPhonology(BaseModel):
    """关卡语音学描述段（可选，内容未填写时不下发）。"""
    ipa: Optional[str] = None                                    # 国际音标，如 "ʈʂ", "ᴀ", "ma˥"
    kind: Optional[Literal["initial", "final", "syllable", "tone"]] = None
    initial: Optional[str] = None                                # 声母键，如 "zh", "b", ""
    final: Optional[str] = None                                  # 韵母键，如 "a", "ang", "iou"
    tones: Optional[List[int]] = None                            # 覆盖声调，如 [1, 2, 3, 4]
    place: Optional[str] = None                                  # 发音部位（双唇/唇齿/舌尖前/舌尖中/舌尖后/舌面/舌根）
    manner: Optional[str] = None                                 # 发音方法（塞音/塞擦音/擦音/鼻音/边音）
    aspiration: Optional[Literal["aspirated", "unaspirated", "none"]] = None
    voicing: Optional[Literal["voiceless", "voiced"]] = None
    hu: Optional[Literal["kaikou", "qichi", "hekou", "cuokou"]] = None
    finalStructure: Optional[Literal["simple", "compound", "front_nasal", "back_nasal", "special"]] = None


class DetectionTask(BaseModel):
    promptText: str
    sampleMediaId: Optional[str] = None
    allowedMetrics: List[str]


class LevelDetail(BaseModel):
    id: str
    order: int
    layer: Literal["vowel", "initial", "syllable"]
    type: str
    targetSound: str
    pinyin: str
    representativeChar: Optional[str] = None
    title: str
    tags: Optional[List[str]] = None
    phonology: Optional[LevelPhonology] = None
    nav: Optional[LevelNav] = None
    articulation: Optional[Articulation] = None
    demos: Optional[List[DemoItem]] = None
    quizzes: Optional[List[QuizQuestion]] = None
    practice: Optional[List[str]] = None
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


class FourStep(BaseModel):
    phenomenon: str
    possibleCause: str
    cue: str
    practice: str
    wordingSource: str


class CurveFrame(BaseModel):
    """原生 10ms 网格绘图帧。"""
    t: float
    hz: Optional[float] = None
    degree: Optional[float] = None
    confidence: float = 0.0
    source: Optional[str] = None
    intensityDb: Optional[float] = None


class ComparisonPoint(BaseModel):
    u: float
    hz: Optional[float] = None
    degree: Optional[float] = None
    confidence: float = 0.0
    source: Optional[str] = None


class CurveFeaturePoint(BaseModel):
    u: Optional[float] = None
    degree: Optional[float] = None
    kind: Optional[str] = None


class CurveQuality(BaseModel):
    validFrames: int
    coverage: float
    jumpDensity: float
    canDiagnose: bool


class SyllableCurveSide(BaseModel):
    """单音节单侧曲线：绘图帧 + 分析区间 + 21 点比较序列 + 调值 + 质量。"""
    frames: Optional[List[CurveFrame]] = None
    t0: Optional[float] = None
    t1: Optional[float] = None
    analysisStart: Optional[float] = None
    analysisEnd: Optional[float] = None
    duration: Optional[float] = None
    analysisDuration: Optional[float] = None
    comparisonPoints: Optional[List[ComparisonPoint]] = None
    chao: Optional[str] = None
    shape: Optional[str] = None
    featurePoints: Optional[dict] = None
    quality: Optional[CurveQuality] = None


class CurveRange(BaseModel):
    fLo: Optional[float] = None
    fHi: Optional[float] = None


class CurveSegment(BaseModel):
    syllable: Optional[str] = None
    toneValue: Optional[float] = None
    user: Optional[SyllableCurveSide] = None
    reference: Optional[SyllableCurveSide] = None


class ResultCurve(BaseModel):
    status: Literal["ok", "not_available"]
    scale: Optional[str] = None
    algorithmVersion: Optional[str] = None
    segments: Optional[List[CurveSegment]] = None
    rangeSnapshotId: Optional[str] = None
    userRange: Optional[CurveRange] = None
    referenceRange: Optional[CurveRange] = None
    sampleMediaId: Optional[str] = None
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


class ScoreBreakdown(BaseModel):
    """分数拆分：声母/韵母/声调为音节级三项判定通过率（主要展示维度），
    overall 为供应商整卷总分（次要）。无音节时分项为空。"""
    overall: float
    initial: Optional[float] = None
    final: Optional[float] = None
    tone: Optional[float] = None


class AssessmentResult(BaseModel):
    levelId: str
    providerVersion: str
    algorithmVersion: str
    quality: Quality
    score: Optional[ScoreBreakdown] = None
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
    score: Optional[ScoreBreakdown] = None


class ArchiveListResponse(BaseModel):
    recordings: Optional[List[ArchiveRecordingSummary]] = None
    nextCursor: Optional[str] = None


class ProgressLevel(BaseModel):
    levelId: str
    completed: bool


class MeProgress(BaseModel):
    levels: List[ProgressLevel]
    nextLevelId: Optional[str] = None


# -------------------------------- 账号 --------------------------------------

class RegisterResponse(BaseModel):
    accountId: str
    username: str
    dialectBackground: Optional[str] = None
    gender: Optional[str] = None


class ProfileResponse(BaseModel):
    """PATCH /api/me/profile 响应：方言区/母语背景与性别设置结果"""
    accountId: str
    username: str
    dialectBackground: Optional[str] = None
    gender: Optional[str] = None


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
