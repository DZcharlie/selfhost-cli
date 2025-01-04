import json
import re
import subprocess
from rich.console import Console

console = Console()

def strip_ansi_escape_sequences(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_terraform_outputs(terraform_dir):
    """Get Terraform outputs as a dictionary."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        outputs = json.loads(result.stdout)
        return {k: v.get('value') for k, v in outputs.items()}
    except subprocess.CalledProcessError as e:
        console.print("[red]Failed to get Terraform outputs[/red]")
        return {}
    except json.JSONDecodeError:
        console.print("[red]Invalid Terraform output format[/red]")
        return {}

def is_retryable_error(error_text):
    """Check if the error is retryable."""
    retryable_errors = [
        "VcpuLimitExceeded",
        "CREATE_FAILED",
        "RequestLimitExceeded",
        "Throttling",
        "ServiceUnavailable"
    ]
    return any(error in error_text for error in retryable_errors) 