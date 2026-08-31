import os
_ACCESS_TOKEN = os.environ["WAPSHOP_ACCESS_TOKEN"]
PAGES = {
    "LANDING5": f"https://wapshop.gameloft.com/demo/t5_test/landing5.php?access_token={_ACCESS_TOKEN}&lan={{lang_id}}",
    "LANDING6": f"https://wapshop.gameloft.com/demo/t5_test/landing6.php?access_token={_ACCESS_TOKEN}&lan={{lang_id}}",
    "PROFILE_SUB": f"https://wapshop.gameloft.com/demo/t5_test/profile.php?agent_uid=wapshop&access_token={_ACCESS_TOKEN}&lan={{lang_id}}",
    "PROFILE_1TIME": f"https://wapshop.gameloft.com/demo/t5_test/profile.php?agent_uid=android&access_token={_ACCESS_TOKEN}&lan={{lang_id}}"
}
