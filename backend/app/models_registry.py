"""导入全部模型，保证 create_all 建全表（models_registry 被 app.db.create_all 引用）。"""
from app.platform.models import AuditLogRow, PreviewTokenRow  # noqa: F401
from app.security_models import AdminSessionRow  # noqa: F401
from app.identity.models import (  # noqa: F401
    AnonSessionRow, AuthSessionRow, ConsentDecisionRow, UserRow, UsernameTombstoneRow,
)
from app.content.models import (  # noqa: F401
    ArticleDraftRow, ArticleRow, ArticleVersionRow, CalibrationTextRow, CategoryRow,
    DetectionSwitchRow, LevelDraftRow, LevelRow, LevelVersionRow, MediaAssetRow,
    MediaRefRow, ReferenceSpeakerRow, SagittalPresetRow,
)
from app.acoustics.models import AudioRow, FeatureCacheRow  # noqa: F401
from app.scoring.models import PitchRangeRow, PitchRangeSnapshotRow, ScoreCacheRow  # noqa: F401
from app.detection.models import AssessmentResultRow, RecordingRow  # noqa: F401
from app.archive.models import LearningEventRow  # noqa: F401
from app.feedback.models import FeedbackRow, WishRow  # noqa: F401
