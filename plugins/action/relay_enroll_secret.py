import shlex

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _supports_check_mode = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if getattr(getattr(self, "_play_context", None), "check_mode", False):
            return {**result, "changed": False, "skipped": True, "msg": "Relay enrollment is skipped in check mode."}
        args = self._task.args
        secret = args.get("secret")
        if not isinstance(secret, str) or not secret.strip():
            return {**result, "failed": True, "msg": "Relay enrollment input is invalid."}
        command = " ".join(
            shlex.quote(value)
            for value in (
                "/usr/bin/python3",
                args["updater"],
                args["config_path"],
                args["station_id"],
                args["key_path"],
            )
        )
        try:
            response = self._low_level_execute_command(
                command,
                in_data=(secret.strip() + "\n").encode("utf-8"),
                sudoable=True,
            )
        except Exception:
            return {**result, "failed": True, "msg": "Relay enrollment command failed."}
        if not isinstance(response, dict):
            return {**result, "failed": True, "msg": "Relay enrollment command failed."}
        try:
            rc = response["rc"]
            stdout = response["stdout"].strip()
        except (KeyError, AttributeError, TypeError):
            return {**result, "failed": True, "msg": "Relay enrollment command failed."}
        if rc != 0 or stdout not in ("changed", "ok"):
            return {**result, "failed": True, "msg": "Relay enrollment command failed."}
        return {**result, "changed": stdout == "changed"}
