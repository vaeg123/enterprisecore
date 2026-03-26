import multiprocessing
import traceback

try:
    multiprocessing.set_start_method("fork")
except RuntimeError:
    pass



# Builtins autorisés (strict minimum)
SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "range": range,
    "print": print
}


def _safe_exec(code: str, return_dict):

    try:
        local_namespace = {}

        exec(
            code,
            {"__builtins__": SAFE_BUILTINS},
            local_namespace
        )

        return_dict["output"] = local_namespace
        return_dict["error"] = None

    except Exception:
        return_dict["output"] = None
        return_dict["error"] = traceback.format_exc()


def code_executor(payload):

    code = payload.get("code")

    if not code:
        return {
            "status": "ERROR",
            "reason": "No code provided"
        }

    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    process = multiprocessing.Process(
        target=_safe_exec,
        args=(code, return_dict)
    )

    process.start()
    process.join(3)  # 3 seconds timeout

    if process.is_alive():
        process.terminate()
        return {
            "status": "TIMEOUT",
            "reason": "Execution exceeded time limit"
        }

    if return_dict["error"]:
        return {
            "status": "ERROR",
            "reason": return_dict["error"]
        }

    return {
        "status": "SUCCESS",
        "result": return_dict["output"]
    }
