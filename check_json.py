import sys
sys.path.insert(0, r'C:\Users\AAWZV\.qclaw\workspace-ua58rsb93veqtxl7\living-paper')
from backend.data.prompts import MACHINE_TAIL_RULE, SOCIETY_BIBLE, AUTONOMY_RULE, PERMADEATH_RULE

rules = [MACHINE_TAIL_RULE, SOCIETY_BIBLE, AUTONOMY_RULE, PERMADEATH_RULE]
for name, rule in [("MACHINE_TAIL_RULE", MACHINE_TAIL_RULE), 
                   ("SOCIETY_BIBLE", SOCIETY_BIBLE),
                   ("AUTONOMY_RULE", AUTONOMY_RULE),
                   ("PERMADEATH_RULE", PERMADEATH_RULE)]:
    has_json = "json" in rule.lower()
    print(f"{name}: contains 'json' = {has_json}")
    if has_json:
        idx = rule.lower().find("json")
        print(f"  context: ...{rule[max(0,idx-20):idx+30]}...")