import winreg

BROWSER_PATH = {
    '360jisu': 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\360chrome.exe',
    'chrome': 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',   
}

def get_browser_path():
    paths_dict = {}
    for name in BROWSER_PATH:
        handler = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, BROWSER_PATH[name], access=winreg.KEY_READ)
        abs_path = winreg.QueryValue(handler, None)
        # print(abs_path)
        paths_dict[name] = abs_path
    return paths_dict
