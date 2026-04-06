import re
import tomllib

from dataclasses import dataclass
from importlib.resources import files


# This file contains workarounds from bad DLNA impementations
# Currently there's 2, both for some JBL devices

# The following is a fix for bad XML sent by JBL devices
def fix_xml(xml_str: str) -> str:
    """
    Fix malformed XML by removing elements with undefined namespaces.
    This is a workaround for DLNA devices that send invalid DIDL-Lite XML.
    """
    if isinstance(xml_str, bytes):
        xml_str = xml_str.decode('utf-8', errors='ignore')
    
    # Find all prefixes used in tags
    prefixes = set()
    for match in re.finditer(r'<(\w+):', xml_str):
        prefixes.add(match.group(1))
    for match in re.finditer(r'</(\w+):', xml_str):
        prefixes.add(match.group(1))

    # Find declared namespaces
    declared = set()
    for match in re.finditer(r'xmlns:(\w+)="[^"]*"', xml_str):
        declared.add(match.group(1))

    undefined = prefixes - declared
    if not undefined:
        return xml_str

    # Remove elements with undefined prefixes
    for prefix in undefined:
        # Remove self-closing tags
        xml_str = re.sub(rf'<{prefix}:[^>]*/>', '', xml_str)
        # Remove opening and closing tags (non-greedy to handle multiple)
        xml_str = re.sub(rf'<{prefix}:[^>]*>.*?</{prefix}:[^>]*>', '', xml_str, flags=re.DOTALL)

    return xml_str

# Patch defusedxml.ElementTree.fromstring
try:
    import defusedxml.ElementTree as defused_ET
    _original_defused_fromstring = defused_ET.fromstring
    
    def _patched_defused_fromstring(text, *args, **kwargs):
        text = fix_xml(text)
        return _original_defused_fromstring(text, *args, **kwargs)
    
    defused_ET.fromstring = _patched_defused_fromstring
except ImportError:
    pass



# # This is a list of which workarounds are needed for what devices
# DEVICE_LIST: dict[str, dict[str, bool]] = {
#     'JBL BAR 500': {'manual_refresh': True, 'always_abs_seek': True, 'rel_seek_is_abs': True},
#     'TX-NR737': {'manual_refresh': True, 'always_abs_seek': True, 'rel_seek_is_abs': False},
#     'default': {'manual_refresh': False, 'always_abs_seek': True, 'rel_seek_is_abs': False} 
#     # Use absolute seek by dafault because relative seek is a mess
# }

_devices_file = (files(__package__) / 'devices.toml').read_text()
_toml_data = tomllib.loads(_devices_file)

@dataclass
class DeviceSpec:
    name: str # Name of device model
    manual_refresh: bool # Request status updates from device instead of relying on notifications
    always_abs_seek: bool # Always use absolute seeking
    rel_seek_is_abs: bool # Send relative seek commands when doing absolute seeking


def _merge_configs(original: dict, override: dict):
    for key, value in override.items():
        if isinstance(value, dict) and key in original:
            _merge_configs(original[key], value)
        else:
            original[key] = value

def load_device_specs(model_name: str) -> DeviceSpec:
    
    
    device_details = None
    default_options = _toml_data['default'].copy()

    for key in _toml_data.keys():
        if _toml_data[key]['name'] == model_name:
            device_details = _toml_data[key].copy()
            break

    if device_details is not None:
        _merge_configs(default_options, device_details)

    return DeviceSpec(**default_options)

KNOWN_DEVICES = _toml_data.keys()
        