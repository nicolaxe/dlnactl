import re

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



# This is a list of devices that require manual status refreshing
MANUAL_REFRESH_DEVICES = [
    'JBL BAR 500'
]