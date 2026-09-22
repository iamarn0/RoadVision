import enum


class VideoStatus(str, enum.Enum):
    UPLOADING = "uploading"
    READY = "ready"
    INVALID = "invalid"
    DELETED = "deleted"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    PROCESSING = "processing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfidenceStatus(str, enum.Enum):
    HIGH_CONFIDENCE = "high_confidence"
    MEDIUM_CONFIDENCE = "medium_confidence"
    LOW_CONFIDENCE = "low_confidence"
    UNCERTAIN = "uncertain"
    NEEDS_VERIFICATION = "needs_verification"


class AssetType(str, enum.Enum):
    ORIGINAL_VIDEO = "original_video"
    ANNOTATED_VIDEO = "annotated_video"
    FULL_FRAME = "full_frame"
    VEHICLE_CROP = "vehicle_crop"
    PLATE_CROP = "plate_crop"
    EXPORT_CSV = "export_csv"
    EXPORT_XLSX = "export_xlsx"
    EXPORT_JSON = "export_json"
    EXPORT_ZIP = "export_zip"


class ExportStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DISTRICT_MASTER = "district_master"
    OPERATOR = "operator"
    AUDITOR = "auditor"
