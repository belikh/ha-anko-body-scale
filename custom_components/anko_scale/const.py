"""Constants for the ANKO Body Scale integration."""

DOMAIN = "anko_scale"

CONF_ADDRESS = "address"
CONF_HEIGHT_CM = "height_cm"
CONF_AGE = "age"
CONF_SEX = "sex"
CONF_PERSONS = "persons"
CONF_PROFILE_ID = "profile_id"
CONF_DISPLAY_NAME = "display_name"
CONF_BIRTH_DATE = "birth_date"
CONF_ATHLETE = "athlete"
CONF_PERSON_ENTITY = "person_entity"
CONF_EXPECTED_WEIGHT = "expected_weight_kg"
CONF_TOLERANCE_KG = "tolerance_kg"
CONF_TOLERANCE_PCT = "tolerance_pct"
CONF_MARGIN_KG = "margin_kg"
CONF_HISTORY_SIZE = "history_size"
CONF_PENDING_TIMEOUT = "pending_timeout_min"
CONF_NOTIFY_SERVICE = "notify_service"

SEX_MALE = "male"
SEX_FEMALE = "female"

DEFAULT_HEIGHT_CM = 170
DEFAULT_AGE = 30
DEFAULT_SEX = SEX_MALE

LEGACY_PROFILE_ID = "legacy"
LEGACY_DISPLAY_NAME = "Person 1"

DEFAULT_TOLERANCE_KG = 5.0
DEFAULT_TOLERANCE_PCT = 7.0
DEFAULT_MARGIN_KG = 2.0
DEFAULT_HISTORY_SIZE = 50
DEFAULT_PENDING_TIMEOUT_MIN = 60

EWMA_ALPHA = 0.3
FORCE_ASSIGN_TIMEOUT_S = 60

# Settling buffer: N consecutive stable frames within SPREAD_KG, finalised
# early once seen; otherwise the last frames are finalised after SETTLE_TIMEOUT_S
# without a new advert.
SETTLE_FRAMES = 3
SETTLE_SPREAD_KG = 0.5
SETTLE_WINDOW_S = 5.0
SETTLE_TIMEOUT_S = 5.0

EVENT_WEIGH_IN = "anko_scale_weigh_in"
EVENT_PENDING = "anko_scale_pending_measurement"

SERVICE_ASSIGN = "assign_measurement"
SERVICE_REASSIGN = "reassign_measurement"
SERVICE_SET_NEXT_PERSON = "set_next_person"
SERVICE_RESET_HISTORY = "reset_person_history"
