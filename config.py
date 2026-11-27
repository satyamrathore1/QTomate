"""
All the settings you need to edit before running the app.
"""

# --- Local repo settings -----------------------------------------------

# REPO_PATH is intentionally NOT set here. It's personal to each team
# member's machine, so it lives in local_settings.py instead (created
# automatically via the app's first-run setup screen, or editable later
# from the sidebar). This keeps config.py identical and shareable across
# the whole team without ever overwriting anyone's own path.
REPO_PATH = ""

# Path to the DEFAULT target .yaml file, RELATIVE TO REPO_PATH above.
# Only used by queue types that don't have an override in
# TEMPLATE_REPO_OVERRIDES below.
YAML_FILE_RELATIVE_PATH = r"SCX\production\services\pro-gke-euwe4-cgeu-1-il-1.yaml"

# The branch you want to branch off from and keep up to date (usually main/master).
BASE_BRANCH = "main"

# The git remote name (almost always "origin").
GIT_REMOTE = "origin"

# --- Dropdown option lists ----------------------------------------------
# Edit these to match your real, fixed lists.

STORE_CODES = [
    "042",
    "059",
    "089",
    "111",
    "222",
    "267",
    "268",
    "415",
    "431",
    "451",
    "453",
    "457",
    "460",
    "462",
    "499",
    "519",
    "529",
    "548",
    "999",
    "1009",
    "1030",
    "1132",
    # add more store codes here
]

REGIONS = [
    "EU", "NA", "AP",
    # add more regions here
]

COUNTRY_CODES = [
    "AU",
    "CA",
    "DE",
    "FR",
    "GB",
    "IT",
    "NL",
    "PT",
    "RO",
    "SE",
    "UK",
    "US",
    # add more country codes here
]

# --- Templates ------------------------------------------------------------

TEMPLATES_DIR = "templates"

# --- Queue type categories --------------------------------------------------
# Groups queue templates into the three sections shown on the frontend.
# Map every template filename (under templates/) to one of the three
# category constants below. Anything left unmapped still shows up in the
# app (under an "Uncategorized" section) instead of silently disappearing -
# so a gap here is visible, not a bug.

CATEGORY_INVENTORY_FUM = "Inventory & FUM"
CATEGORY_INBOUND_OUTBOUND = "Inbound & Outbound"
CATEGORY_GOODS_MOVEMENT = "Goods Movement"
CATEGORY_TRANSACTIONAL_CONSUMER = "Transactional Consumer"

# The order the three dropdowns appear in on the page.
CATEGORY_ORDER = [CATEGORY_INVENTORY_FUM, CATEGORY_INBOUND_OUTBOUND, CATEGORY_GOODS_MOVEMENT, CATEGORY_TRANSACTIONAL_CONSUMER]

TEMPLATE_CATEGORIES = {
    # TODO: assign each of these (and any future template) to whichever of
    # the three categories above it actually belongs to - these are just
    # placeholders so nothing is left unmapped.
        
    "FCCS_MHS_GIS_snapshot.txt": CATEGORY_INVENTORY_FUM,
    "FCCS_POSLogV2.txt": CATEGORY_INVENTORY_FUM,
    "FCCS_SGF_TBU_StoreStructureV1.txt": CATEGORY_INVENTORY_FUM,
    "FCCS_SLM_StoreStructureV1.txt": CATEGORY_INVENTORY_FUM,
    "FCCS_SLM_TBU_StoreStructureV1.txt": CATEGORY_INVENTORY_FUM,
    "ITEM_RANGE_&_SALES_STOP(Non-Owner-Publisher-ERIX).txt": CATEGORY_INVENTORY_FUM,
    "ITEM_RANGE_UPDATED_V1.txt": CATEGORY_INVENTORY_FUM,
    "MASTER_CONSUMER_V1(Artilce_Master).txt": CATEGORY_INVENTORY_FUM,
    "SALES_STOP_UPDATED_V1.txt": CATEGORY_INVENTORY_FUM,
    "ERIX_ACL_Profile.txt": CATEGORY_INVENTORY_FUM,
    "DSMLH_CONSIGNMENT_UPDATES.txt": CATEGORY_INBOUND_OUTBOUND,
    "Outbound_Queues(Release,FOE,Pick-Up).txt": CATEGORY_INBOUND_OUTBOUND,
    "FOE_PICK_ORDER_CONSUMER_V1.txt": CATEGORY_INBOUND_OUTBOUND,
    "PICK_UP_POINT_LOCKERS_CONSUMER_V1.txt": CATEGORY_INBOUND_OUTBOUND,
    "RELEASE_ORDER_CONSUMER_V1.txt": CATEGORY_INBOUND_OUTBOUND,
    "OLM_ORDERLINES_PREDICTED.txt": CATEGORY_INBOUND_OUTBOUND,
    "FLT_IntegrationService_Dwp_Slm_Item.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_IntegrationService_SCE_Stock.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_IntegrationService_Store_Structure_BaseLoad.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_IntegrationService_Store_Structure_Created.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_IntegrationService_Store_Structure_Deleted.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_IntegrationService_Store_Structure_Updated.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_15.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_27.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_48.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_68.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_72.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_75_New.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_75_Old.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_11.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_A.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_B.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_C.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_D.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_242_E.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_322.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_Linehaul_Consignment_324.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_SDS_OperationalForecastDay.txt": CATEGORY_GOODS_MOVEMENT,
    "FLT_SDS_SafetyStockWeek.txt": CATEGORY_GOODS_MOVEMENT,
    "TRANSACTIONAL_CONSUMER_V1_TOPOLOGY(Pre_Cutover).txt": CATEGORY_TRANSACTIONAL_CONSUMER,
    "TRANSACTIONAL_CONSUMER_V1_INVENTORY(Pre_Cutover).txt": CATEGORY_TRANSACTIONAL_CONSUMER,
    "TRANSACTIONAL_CONSUMER_V1_REPLENISHMENT_PRENOTE(Pre-Cutover).txt": CATEGORY_TRANSACTIONAL_CONSUMER,
    "TRANSACTIONAL_CONSUMER_V1_FMSRR(Cutover-Night).txt": CATEGORY_TRANSACTIONAL_CONSUMER,
    "TRANSACTIONAL_CONSUMER_V1_STOCK-UPDATE_iRECOVER(Cutover-Night).txt": CATEGORY_TRANSACTIONAL_CONSUMER,

}

# --- Per-queue-type repo overrides -----------------------------------------
# IMPORTANT: "yaml_relative_path" here is ALWAYS relative to that entry's
# "repo_path" (or to REPO_PATH above, if no repo_path override is given) -
# never paste a full C:\... path. Using a real relative path means this
# whole file only needs REPO_PATH updated in one place if the repo ever
# moves or gets cloned somewhere else.
#
# Only set "repo_path" for a queue type if it genuinely lives in a
# DIFFERENT repository than REPO_PATH. Leave it out (as below) when it's
# the same repo, just a different file - it'll fall back automatically.

# These five queue types all share the same FCCS service file - defined
# once here so there's only one place to update if that path ever changes.
_FCCS_SERVICES_FILE = r"FCCS\production\services\pro-gke-euwe4-cgeu-1-il-1.yaml"
_FLT_SERVICES_FILE = r"FLT\production\services\pro-gke-euwe4-cgeu-1-il-1.yaml"

TEMPLATE_REPO_OVERRIDES = {
    "ITEM_RANGE_&_SALES_STOP(Non-Owner-Publisher-ERIX).txt": {
        "yaml_relative_path": r"SCX\production\non-owner-queue-publishers.yaml",
        "blank_line_separator": False,
        "sort_by_store": True,
    },
    "FCCS_MHS_GIS_snapshot.txt": {
        "yaml_relative_path": _FCCS_SERVICES_FILE,
    },
    "FCCS_POSLogV2.txt": {
        "yaml_relative_path": _FCCS_SERVICES_FILE,
    },
    "FCCS_SGF_TBU_StoreStructureV1.txt": {
        "yaml_relative_path": _FCCS_SERVICES_FILE,
    },
    "FCCS_SLM_StoreStructureV1.txt": {
        "yaml_relative_path": _FCCS_SERVICES_FILE,
    },
    "FCCS_SLM_TBU_StoreStructureV1.txt": {
        "yaml_relative_path": _FCCS_SERVICES_FILE,
    },
    "ERIX_ACL_Profile.txt": {
        "yaml_relative_path": r"ERIX\production\acl-profile.yaml",
        "sort_by_store": True,
    },
    "FLT_IntegrationService_Dwp_Slm_Item.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_IntegrationService_SCE_Stock.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
        "sort_by_store": True,
    },
    "FLT_IntegrationService_Store_Structure_BaseLoad.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_IntegrationService_Store_Structure_Created.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_IntegrationService_Store_Structure_Deleted.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_IntegrationService_Store_Structure_Updated.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_15.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_27.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_48.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_68.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_72.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_75_New.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_75_Old.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_11.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_A.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_B.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_C.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_D.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_242_E.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_322.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_Linehaul_Consignment_324.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_SDS_OperationalForecastDay.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
    "FLT_SDS_SafetyStockWeek.txt": {
        "yaml_relative_path": _FLT_SERVICES_FILE,
    },
}


def get_repo_settings(template_name):
    """
    Return the effective {repo_path, yaml_relative_path, base_branch, remote,
    blank_line_separator, sort_by_store} for a given template filename -
    the override if one is set, otherwise the defaults above.

    blank_line_separator controls whether a NEW entry gets a blank line
    before/after it when inserted into a cluster of similar entries.
    Defaults to True (matches most files' convention) - set it to False
    per-template in TEMPLATE_REPO_OVERRIDES for target files that pack
    entries with no blank lines between them.

    sort_by_store controls whether new entries get inserted in numeric
    store order (e.g. store 450 lands between 400 and 500) instead of
    always being appended after the last existing entry. Defaults to
    False - set it to True per-template for files that must stay sorted.
    """
    override = TEMPLATE_REPO_OVERRIDES.get(template_name, {})
    return {
        "repo_path": override.get("repo_path", REPO_PATH),
        "yaml_relative_path": override.get("yaml_relative_path", YAML_FILE_RELATIVE_PATH),
        "base_branch": override.get("base_branch", BASE_BRANCH),
        "remote": override.get("remote", GIT_REMOTE),
        "blank_line_separator": override.get("blank_line_separator", True),
        "sort_by_store": override.get("sort_by_store", False),
    }