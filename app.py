import datetime
import importlib.util
import re
import sys
from pathlib import Path

import streamlit as st

# --- Locate the app's real "home" folder ------------------------------------
# When run as a normal Python script, that's this file's own folder. When run
# as a packaged .exe (PyInstaller), sys.executable is the .exe itself, and
# its folder is where config.py / templates / local_settings.py must live as
# plain editable files sitting NEXT TO the exe - never bundled inside it,
# or the store/country-code editor and template updates would silently stop
# working (the frozen exe would keep using whatever was baked in at build
# time, no matter what gets "written" at runtime).
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE_PATH = BASE_DIR / "config.py"
LOCAL_SETTINGS_FILE_PATH = BASE_DIR / "local_settings.py"


def _load_module_from_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_config():
    return _load_module_from_path("config", CONFIG_FILE_PATH)


def load_local_settings():
    if not LOCAL_SETTINGS_FILE_PATH.exists():
        LOCAL_SETTINGS_FILE_PATH.write_text(
            '"""\n'
            "Personal settings for THIS laptop only - not meant to be shared with\n"
            "teammates or overwritten when config.py/templates are updated.\n"
            '"""\n\n'
            '# Absolute path to YOUR local clone of the repo.\n'
            'REPO_PATH = ""\n',
            encoding="utf-8",
        )
    return _load_module_from_path("local_settings", LOCAL_SETTINGS_FILE_PATH)


config = load_config()
local_settings = load_local_settings()

import git_ops  # noqa: E402  (git_ops has no per-user state, fine to import normally)

st.set_page_config(page_title="Q-Tomate", page_icon="🍅", layout="centered")

# --- First-run setup: make sure we know where the repo is on THIS machine ---

if not getattr(local_settings, "REPO_PATH", "").strip():
    st.markdown(
        """
        <div class="qtomate-header" style="display:flex;align-items:baseline;gap:10px;">
            <h1 style="margin:0;font-size:2.2rem;">🍅 Q-Tomate</h1>
            <span style="color:#888;font-size:0.85rem;font-style:italic;">by Satyam</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("👋 First-time setup")
    st.write(
        "Before you start, tell Q-Tomate where your local clone of the repo lives "
        "on this computer. You only need to do this once."
    )
    repo_path_input = st.text_input(
        "Local repo path",
        placeholder=r"C:\Users\yourname\Documents\FMS Git Repo\event-mesh-clients",
        help="The folder on YOUR machine where you've already git-cloned the repo.",
    )
    if st.button("Save and continue", type="primary"):
        val = repo_path_input.strip()
        if not val:
            st.warning("Enter a path first.")
        elif not Path(val).exists():
            st.warning(f"That path doesn't exist on this machine: {val}")
        elif not (Path(val) / ".git").exists():
            st.warning(f"That folder doesn't look like a git repo (no .git found): {val}")
        else:
            LOCAL_SETTINGS_FILE_PATH.write_text(
                '"""\n'
                "Personal settings for THIS laptop only - not meant to be shared with\n"
                "teammates or overwritten when config.py/templates are updated.\n"
                '"""\n\n'
                '# Absolute path to YOUR local clone of the repo.\n'
                f'REPO_PATH = r"{val}"\n',
                encoding="utf-8",
            )
            st.success("Saved!")
            st.rerun()
    st.stop()

config.REPO_PATH = local_settings.REPO_PATH

# --- Light visual polish (safe, minimal CSS) --------------------------------

st.markdown(
    """
    <style>
    .qtomate-header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 0; }
    .qtomate-header h1 { margin: 0; font-size: 2.2rem; }
    .qtomate-tagline { color: #888; font-size: 0.85rem; font-style: italic; }
    .qtomate-subtitle { color: #888; margin-top: 2px; margin-bottom: 1.2rem; }
    div[data-testid="stExpander"] { border-radius: 10px; }
    div.stButton > button[kind="primary"] { border-radius: 8px; font-weight: 600; }
    footer.qtomate-footer { text-align: center; color: #999; font-size: 0.8rem; margin-top: 2.5rem; }
    </style>
    <div class="qtomate-header">
        <h1>🍅 Q-Tomate</h1>
        <span class="qtomate-tagline">by Satyam</span>
    </div>
    <div class="qtomate-subtitle">Add queues &amp; subscriptions to your YAML configs and ship straight to a PR.</div>
    """,
    unsafe_allow_html=True,
)

# --- Helpers to add/remove store & country codes from config.py itself ----


def sorted_store_codes(codes):
    """Numeric ascending (so '089' < '267' < '1009'), not plain string sort."""
    def key(code):
        try:
            return (0, int(code))
        except ValueError:
            return (1, code)  # non-numeric codes sort after, alphabetically
    return sorted(codes, key=key)


def sorted_alpha(values):
    """Case-insensitive alphabetical sort."""
    return sorted(values, key=str.upper)


def _format_list_literal(var_name, values, trailing_comment):
    lines = [f"{var_name} = ["]
    for v in values:
        lines.append(f'    "{v}",')
    lines.append(f"    # {trailing_comment}")
    lines.append("]")
    return "\n".join(lines)


def update_config_list(var_name, values, trailing_comment):
    """Rewrite just the STORE_CODES / COUNTRY_CODES block inside config.py on
    disk, then reload the config module so this run picks up the change."""
    global config
    text = CONFIG_FILE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"{var_name} = \[.*?\]", re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"Could not find '{var_name}' in config.py to update.")
    new_block = _format_list_literal(var_name, values, trailing_comment)
    new_text = pattern.sub(lambda m: new_block, text, count=1)
    CONFIG_FILE_PATH.write_text(new_text, encoding="utf-8")
    config = load_config()
    config.REPO_PATH = local_settings.REPO_PATH


CATEGORY_ICONS = {
    getattr(config, "CATEGORY_INVENTORY_FUM", None): "📦",
    getattr(config, "CATEGORY_INBOUND_OUTBOUND", None): "🚚",
    getattr(config, "CATEGORY_GOODS_MOVEMENT", None): "📋",
}

with st.sidebar:
    with st.expander("📁 Repo path (this computer)"):
        st.caption(f"Currently: `{local_settings.REPO_PATH}`")
        new_repo_path = st.text_input("Change repo path", key="change_repo_path_input")
        if st.button("Save", key="save_repo_path_btn"):
            val = new_repo_path.strip()
            if not val:
                st.warning("Enter a path first.")
            elif not Path(val).exists():
                st.warning(f"That path doesn't exist on this machine: {val}")
            elif not (Path(val) / ".git").exists():
                st.warning(f"That folder doesn't look like a git repo (no .git found): {val}")
            else:
                LOCAL_SETTINGS_FILE_PATH.write_text(
                    '"""\n'
                    "Personal settings for THIS laptop only - not meant to be shared with\n"
                    "teammates or overwritten when config.py/templates are updated.\n"
                    '"""\n\n'
                    '# Absolute path to YOUR local clone of the repo.\n'
                    f'REPO_PATH = r"{val}"\n',
                    encoding="utf-8",
                )
                st.success("Saved!")
                st.rerun()

    st.markdown("### 🛠️ Manage dropdown lists")
    st.caption("Changes here are saved straight to config.py and apply immediately.")

    with st.expander("🏬 Store codes"):
        new_store = st.text_input("Add store code", key="new_store_code_input")
        if st.button("➕ Add", key="add_store_btn"):
            val = new_store.strip()
            if not val:
                st.warning("Enter a store code first.")
            elif val in config.STORE_CODES:
                st.warning(f"'{val}' is already in the list.")
            else:
                update_config_list(
                    "STORE_CODES", sorted_store_codes(config.STORE_CODES + [val]), "add more store codes here"
                )
                st.success(f"Added '{val}'.")
                st.rerun()

        if config.STORE_CODES:
            remove_store = st.selectbox(
                "Remove store code", sorted_store_codes(config.STORE_CODES), key="remove_store_select"
            )
            if st.button("🗑️ Remove", key="remove_store_btn"):
                if len(config.STORE_CODES) == 1:
                    st.warning("Can't remove the last store code - at least one is required.")
                else:
                    updated = sorted_store_codes([s for s in config.STORE_CODES if s != remove_store])
                    update_config_list("STORE_CODES", updated, "add more store codes here")
                    st.success(f"Removed '{remove_store}'.")
                    st.rerun()

    with st.expander("🌍 Country codes"):
        new_country = st.text_input("Add country code", key="new_country_code_input")
        if st.button("➕ Add", key="add_country_btn"):
            val = new_country.strip().upper()
            if not val:
                st.warning("Enter a country code first.")
            elif val in config.COUNTRY_CODES:
                st.warning(f"'{val}' is already in the list.")
            else:
                update_config_list(
                    "COUNTRY_CODES", sorted_alpha(config.COUNTRY_CODES + [val]), "add more country codes here"
                )
                st.success(f"Added '{val}'.")
                st.rerun()

        if config.COUNTRY_CODES:
            remove_country = st.selectbox(
                "Remove country code", sorted_alpha(config.COUNTRY_CODES), key="remove_country_select"
            )
            if st.button("🗑️ Remove", key="remove_country_btn"):
                if len(config.COUNTRY_CODES) == 1:
                    st.warning("Can't remove the last country code - at least one is required.")
                else:
                    updated = sorted_alpha([c for c in config.COUNTRY_CODES if c != remove_country])
                    update_config_list("COUNTRY_CODES", updated, "add more country codes here")
                    st.success(f"Removed '{remove_country}'.")
                    st.rerun()

# --- Load available templates -------------------------------------------

templates_dir = BASE_DIR / config.TEMPLATES_DIR
template_files = sorted(p.name for p in templates_dir.glob("*.txt"))

if not template_files:
    st.error(f"No template files found in '{templates_dir}'. Add some .txt templates first.")
    st.stop()

# --- Form -----------------------------------------------------------------

st.markdown("#### 🗂️ Queue types")
st.caption(
    "Select one or more items to add in this run. Each goes to its configured repo "
    "automatically - if that spans more than one repo, one branch/commit/push (and PR) "
    "is created per repo. Items marked *(subscriptions only)* or *(list entry only)* "
    "add into something that already exists, instead of creating a new queue."
)


def render_template_checkbox(name):
    label = name.replace(".txt", "")
    template_text = (templates_dir / name).read_text(encoding="utf-8")
    if git_ops.is_subscription_template(template_text):
        label += "  (subscriptions only)"
    elif git_ops.is_replace_subscriptions_template(template_text):
        label += "  (⚠️ replaces subscriptions)"
    elif git_ops.is_list_append_template(template_text):
        label += "  (list entry only)"
    return st.checkbox(label, key=f"tpl_{name}")


def _set_checkboxes(names, value):
    for name in names:
        st.session_state[f"tpl_{name}"] = value


# Group templates by their configured category, preserving CATEGORY_ORDER.
# Anything not mapped in config.TEMPLATE_CATEGORIES still shows up (under
# "Uncategorized") instead of silently disappearing.
categorized = {cat: [] for cat in config.CATEGORY_ORDER}
uncategorized = []
for name in template_files:
    cat = config.TEMPLATE_CATEGORIES.get(name)
    if cat in categorized:
        categorized[cat].append(name)
    else:
        uncategorized.append(name)

selected_templates = []

for cat in config.CATEGORY_ORDER:
    names = categorized[cat]
    icon = CATEGORY_ICONS.get(cat, "🔹")
    with st.expander(f"{icon} {cat} ({len(names)})"):
        if not names:
            st.caption("No queue types assigned to this category yet.")
        else:
            btn_col1, btn_col2 = st.columns(2)
            btn_col1.button(
                "☑️ Select all", key=f"selectall_{cat}", use_container_width=True,
                on_click=_set_checkboxes, args=(names, True),
            )
            btn_col2.button(
                "⬜ Clear", key=f"clearall_{cat}", use_container_width=True,
                on_click=_set_checkboxes, args=(names, False),
            )
        for name in names:
            if render_template_checkbox(name):
                selected_templates.append(name)

if uncategorized:
    with st.expander(f"❓ Uncategorized ({len(uncategorized)})"):
        st.caption("These aren't assigned to a category in config.py (TEMPLATE_CATEGORIES) yet.")
        btn_col1, btn_col2 = st.columns(2)
        btn_col1.button(
            "☑️ Select all", key="selectall_uncategorized", use_container_width=True,
            on_click=_set_checkboxes, args=(uncategorized, True),
        )
        btn_col2.button(
            "⬜ Clear", key="clearall_uncategorized", use_container_width=True,
            on_click=_set_checkboxes, args=(uncategorized, False),
        )
        for name in uncategorized:
            if render_template_checkbox(name):
                selected_templates.append(name)

st.markdown("#### 📍 Store, region & country")
col1, col2, col3 = st.columns(3)
with col1:
    store_code = st.selectbox("Store code", sorted_store_codes(config.STORE_CODES), help="The store this addition applies to.")
with col2:
    region = st.selectbox("Region", sorted_alpha(config.REGIONS), help="Substituted wherever {REGION} appears in the template.")
with col3:
    country_code = st.selectbox("Country code", sorted_alpha(config.COUNTRY_CODES), help="Substituted wherever {COUNTRY} appears in the template.")

if not selected_templates:
    st.info("☝️ Select at least one queue type above to see a preview.")
    st.stop()

# --- Render preview for each selected template, with resolved repo --------

items = []  # list of dicts, one per selected template

for name in selected_templates:
    template_path = templates_dir / name
    template_text = template_path.read_text(encoding="utf-8")
    repo_settings = config.get_repo_settings(name)

    if git_ops.is_subscription_template(template_text):
        target_queue_name, body_template = git_ops.parse_subscription_template(template_text)
        target_queue_name = (
            target_queue_name
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        rendered_lines = (
            body_template
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        items.append({
            "name": name,
            "type": "subscription",
            "target_queue_name": target_queue_name,
            "rendered_lines": rendered_lines,
            "template_body": body_template,
            "repo_settings": repo_settings,
        })
    elif git_ops.is_replace_subscriptions_template(template_text):
        target_queue_name, body_template = git_ops.parse_replace_subscriptions_template(template_text)
        target_queue_name = (
            target_queue_name
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        rendered_lines = (
            body_template
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        items.append({
            "name": name,
            "type": "replace_subscriptions",
            "target_queue_name": target_queue_name,
            "rendered_lines": rendered_lines,
            "repo_settings": repo_settings,
        })
    elif git_ops.is_list_append_template(template_text):
        body_template = git_ops.parse_list_append_template(template_text)
        rendered_lines = (
            body_template
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        items.append({
            "name": name,
            "type": "list_line",
            "template_body": body_template,
            "rendered_lines": rendered_lines,
            "repo_settings": repo_settings,
        })
    else:
        rendered_block = (
            template_text
            .replace("{STORE}", store_code)
            .replace("{REGION}", region)
            .replace("{COUNTRY}", country_code)
        )
        items.append({
            "name": name,
            "type": "queue",
            "template_text": template_text,
            "block_text": rendered_block,
            "repo_settings": repo_settings,
        })

# Two different groupings:
# - display_groups: by (repo, file) - purely for showing the preview clearly.
# - exec_groups: by (repo, base_branch, remote) ONLY - this is what actually
#   runs. All items for the same repo MUST go through a single pull/branch/
#   commit/push cycle, even if they touch different files in that repo -
#   otherwise a second pass resets the local branch from main again and the
#   push fails as non-fast-forward.
def display_key(item):
    rs = item["repo_settings"]
    return (rs["repo_path"], rs["yaml_relative_path"])

def exec_key(item):
    rs = item["repo_settings"]
    return (rs["repo_path"], rs["base_branch"], rs["remote"])

display_groups = {}
for item in items:
    display_groups.setdefault(display_key(item), []).append(item)

exec_groups = {}
for item in items:
    exec_groups.setdefault(exec_key(item), []).append(item)

TYPE_ICONS = {"queue": "🆕", "subscription": "📝", "list_line": "➕", "replace_subscriptions": "⚠️"}

st.markdown("#### 🔍 Preview")
for (repo_path, yaml_relative_path), group_items in display_groups.items():
    with st.container(border=True):
        st.markdown(f"**📁 Repo:** `{repo_path}`  \n**📄 File:** `{yaml_relative_path}`")
        for item in group_items:
            icon = TYPE_ICONS.get(item["type"], "🔹")
            with st.expander(f"{icon} {item['name'].replace('.txt', '')}", expanded=(len(items) == 1)):
                if item["type"] == "subscription":
                    st.caption(f"Adding to existing queue: `{item['target_queue_name']}`")
                    st.code(item["rendered_lines"], language="yaml")
                elif item["type"] == "replace_subscriptions":
                    st.warning(
                        f"This will **remove all existing subscriptions** of "
                        f"`{item['target_queue_name']}` and replace them with the lines below."
                    )
                    st.code(item["rendered_lines"], language="yaml")
                elif item["type"] == "list_line":
                    st.caption("Adding after the last matching line in this list.")
                    st.code(item["rendered_lines"], language="yaml")
                else:
                    st.code(item["block_text"], language="yaml")

# --- Branch name / commit message -----------------------------------------

st.markdown("#### 🔧 Branch & commit")


def sanitize_branch_component(text):
    """
    Make a string safe to use inside a git branch name. Git branch names
    can't contain spaces or several special characters (parentheses,
    commas, colons, etc.) - template filenames like
    'Outbound_Queues(Release, FOE, Pick-Up)' aren't valid on their own,
    so strip anything not alphanumeric/dash/underscore/dot down to dashes.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-.")
    return cleaned or "queue"


queue_short_names = [item["name"].replace(".txt", "") for item in items]
safe_queue_names = [sanitize_branch_component(n) for n in queue_short_names]
run_suffix = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

if len(queue_short_names) == 1:
    default_branch_name = f"add-queue-{safe_queue_names[0]}-{store_code}-{region}-{run_suffix}".lower()
    default_commit_message = (
        f"Add {queue_short_names[0]} queue/subscriptions for store {store_code} ({region})"
    )
else:
    default_branch_name = f"add-queues-{store_code}-{region}-{run_suffix}".lower()
    default_commit_message = (
        f"Add {', '.join(queue_short_names)} queue/subscriptions for store {store_code} ({region})"
    )
default_branch_name = sanitize_branch_component(default_branch_name)

branch_name = st.text_input("Feature branch name (used in every repo involved)", value=default_branch_name)
st.caption("A timestamp is appended by default so re-running this tool never collides with an earlier, still-open branch/PR. Feel free to edit it.")
commit_message = st.text_input("Commit message", value=default_commit_message)

st.divider()

# --- Duplicate check (against each repo's local file) ----------------------

force_add = False
any_duplicates = False
for (repo_path, base_branch, remote), group_items in exec_groups.items():
    dups = git_ops.find_duplicates_multi(
        repo_path,
        [{**item, "yaml_relative_path": item["repo_settings"]["yaml_relative_path"]} for item in group_items],
    )
    if dups:
        any_duplicates = True
        count_label = "1 entry" if len(dups) == 1 else f"{len(dups)} entries"
        st.warning(
            f"⚠️ In `{repo_path}`, {count_label} already exist:\n\n"
            + "\n".join(f"- `{n}`" for n in dups)
        )

if any_duplicates:
    force_add = st.checkbox(
        "Add anyway (skip duplicate check, applies to all repos in this run)"
    )

# --- Confirm destructive "replace subscriptions" items ---------------------

replace_items = [item for item in items if item["type"] == "replace_subscriptions"]
confirm_replace = True
if replace_items:
    queue_list = ", ".join(f"`{item['target_queue_name']}`" for item in replace_items)
    st.warning(
        f"⚠️ This run will **permanently remove and replace** all existing "
        f"subscriptions for: {queue_list}. This can't be undone by this tool "
        "once pushed - review the preview above carefully."
    )
    confirm_replace = st.checkbox(
        "I understand this will delete the existing subscriptions listed above"
    )

# --- Execute ---------------------------------------------------------------

execute_clicked = st.button(
    "🚀 Execute", type="primary", use_container_width=True,
    disabled=bool(replace_items) and not confirm_replace,
)

if execute_clicked:
    overall_success = True

    for (repo_path, base_branch, remote), group_items in exec_groups.items():

        with st.status(f"📁 {repo_path}", expanded=True) as status:

            def log(msg, _status=status):
                _status.write(msg)

            # Build the plain item dicts run_full_workflow expects (drop UI-only keys)
            workflow_items = []
            for item in group_items:
                yaml_relative_path = item["repo_settings"]["yaml_relative_path"]
                if item["type"] == "subscription":
                    workflow_items.append({
                        "type": "subscription",
                        "yaml_relative_path": yaml_relative_path,
                        "target_queue_name": item["target_queue_name"],
                        "rendered_lines": item["rendered_lines"],
                        "template_body": item.get("template_body"),
                        "sort_by_store": item["repo_settings"].get("sort_by_store", False),
                        "new_store": store_code,
                    })
                elif item["type"] == "replace_subscriptions":
                    workflow_items.append({
                        "type": "replace_subscriptions",
                        "yaml_relative_path": yaml_relative_path,
                        "target_queue_name": item["target_queue_name"],
                        "rendered_lines": item["rendered_lines"],
                    })
                elif item["type"] == "list_line":
                    workflow_items.append({
                        "type": "list_line",
                        "yaml_relative_path": yaml_relative_path,
                        "template_body": item["template_body"],
                        "rendered_lines": item["rendered_lines"],
                        "sort_by_store": item["repo_settings"].get("sort_by_store", False),
                        "new_store": store_code,
                    })
                else:
                    workflow_items.append({
                        "type": "queue",
                        "yaml_relative_path": yaml_relative_path,
                        "template_text": item["template_text"],
                        "block_text": item["block_text"],
                        "blank_line_separator": item["repo_settings"].get("blank_line_separator", True),
                        "sort_by_store": item["repo_settings"].get("sort_by_store", False),
                        "new_store": store_code,
                    })

            try:
                git_ops.run_full_workflow(
                    repo_path=repo_path,
                    remote=remote,
                    base_branch=base_branch,
                    branch_name=branch_name,
                    items=workflow_items,
                    commit_message=commit_message,
                    log=log,
                    force=force_add,
                )
                status.update(label=f"✅ Pushed to {repo_path}", state="complete")
                st.success(
                    f"Pushed branch **{branch_name}** to `{repo_path}`. "
                    "Go to GitHub to open the pull request."
                )
            except git_ops.DuplicateEntryError as e:
                overall_success = False
                status.update(label=f"⚠️ Duplicate entries in {repo_path}", state="error")
                st.error(str(e))
            except git_ops.GitOpsError as e:
                overall_success = False
                status.update(label=f"❌ Failed for {repo_path}", state="error")
                st.error(str(e))

    if overall_success:
        st.balloons()

st.markdown('<footer class="qtomate-footer">🍅 Q-Tomate &middot; by Satyam</footer>', unsafe_allow_html=True)