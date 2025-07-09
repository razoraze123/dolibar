import sys
import types

# Provide minimal fake selenium and webdriver_manager modules so that
# project modules can be imported without the real dependencies.
selenium = types.ModuleType("selenium")
webdriver_mod = types.ModuleType("webdriver")
selenium.webdriver = webdriver_mod
sys.modules.setdefault("selenium", selenium)
sys.modules.setdefault("selenium.webdriver", webdriver_mod)

# webdriver.common.by
common_mod = types.ModuleType("common")
by_mod = types.ModuleType("by")
by_mod.By = types.SimpleNamespace(CSS_SELECTOR="CSS")
webdriver_mod.common = common_mod
common_mod.by = by_mod
sys.modules.setdefault("selenium.webdriver.common", common_mod)
sys.modules.setdefault("selenium.webdriver.common.by", by_mod)

# webdriver.support
support_mod = types.ModuleType("support")
ui_mod = types.ModuleType("ui")
ui_mod.WebDriverWait = object
ec_mod = types.ModuleType("expected_conditions")
webdriver_mod.support = support_mod
support_mod.ui = ui_mod
support_mod.expected_conditions = ec_mod
sys.modules.setdefault("selenium.webdriver.support", support_mod)
sys.modules.setdefault("selenium.webdriver.support.ui", ui_mod)
sys.modules.setdefault("selenium.webdriver.support.expected_conditions", ec_mod)

# webdriver.chrome
chrome_mod = types.ModuleType("chrome")
options_mod = types.ModuleType("options")
options_mod.Options = object
service_mod = types.ModuleType("service")
service_mod.Service = object
chrome_mod.options = options_mod
chrome_mod.service = service_mod
webdriver_mod.chrome = chrome_mod
sys.modules.setdefault("selenium.webdriver.chrome", chrome_mod)
sys.modules.setdefault("selenium.webdriver.chrome.options", options_mod)
sys.modules.setdefault("selenium.webdriver.chrome.service", service_mod)

# webdriver_manager.chrome
wm_mod = types.ModuleType("webdriver_manager.chrome")
class DummyCDM:
    def install(self):
        return "/tmp/chromedriver"
wm_mod.ChromeDriverManager = DummyCDM
sys.modules.setdefault("webdriver_manager.chrome", wm_mod)

# Dummy requests and tqdm modules
requests_mod = types.ModuleType("requests")
sys.modules.setdefault("requests", requests_mod)

tqdm_mod = types.ModuleType("tqdm")
tqdm_mod.tqdm = lambda x, **k: x
sys.modules.setdefault("tqdm", tqdm_mod)

# Ensure project root is on sys.path for module imports
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
