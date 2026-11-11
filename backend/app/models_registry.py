"""导入全部模型，保证 create_all 建全表（models_registry 被 app.db.create_all 引用）。"""
from app.identity.models import SessionRow, UserRow  # noqa: F401
from app.content.models import (  # noqa: F401
    ArticleRow, CalibrationTextRow, CategoryRow, LevelConfusableRow, LevelRow,
    MediaAssetRow, ReferenceSpeakerRow,
)
from app.acoustics.models import AudioRow, FeatureCacheRow  # noqa: F401
from app.scoring.models import (  # noqa: F401
    CalibrationSessionRow, CalibrationTakeRow, PitchRangeRow, ScoreCacheRow,
)
from app.detection.models import RecordingRow  # noqa: F401
from app.feedback.models import FeedbackRow  # noqa: F401
