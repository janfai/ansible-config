import shlex

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
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
        if response.rc != 0 or response.stdout.strip() not in ("changed", "ok"):
            return {**result, "failed": True, "msg": "Relay enrollment command failed."}
        return {**result, "changed": response.stdout.strip() == "changed"}
