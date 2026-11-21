from typing import Optional, Dict

def parse_simulate_failure_header(header_value: Optional[str], enabled: bool) -> Dict[str, int]:
    """
    Parses X-Simulate-Failure header if ENABLE_FAILURE_SIMULATION is true.
    Format: comma-separated <key_id>=<status> pairs; '*' means every key.
    Statuses: 429, 500, 502, 503.
    Examples:
      'key_1=429'
      'key_1=429,key_2=500'
      '*=429'
    """
    if not enabled or not header_value:
        return {}
    
    simulations: Dict[str, int] = {}
    parts = [p.strip() for p in header_value.split(",") if p.strip()]
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            try:
                status = int(v)
                if status in (429, 500, 502, 503):
                    simulations[k] = status
            except ValueError:
                continue
    return simulations

def get_simulated_status(key_id: str, simulations: Dict[str, int]) -> Optional[int]:
    """
    Returns simulated status code if key is simulated to fail, else None.
    '*' overrides or applies to all keys.
    """
    if "*" in simulations:
        return simulations["*"]
    return simulations.get(key_id)
