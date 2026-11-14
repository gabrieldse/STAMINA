import spiceypy as sp

def get_et(time_string,verbose=False):
    try:
        return sp.str2et(time_string)
    except Exception as e:
        if verbose:
            print(f"UTC time string format is invalid: {e}")
            print(f"Time string format should be 'YYYY-MM-DDTHH:MM:SS'")
        return None

def get_UTC(et, verbose=False):
    try:
        return sp.et2utc(et, "C", 0)
    except Exception as e:
        if verbose:
            print(f"Error converting ephemeris time to UTC: {e}")
        return None