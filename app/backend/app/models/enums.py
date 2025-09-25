import enum

class InstanceStatus(str, enum.Enum):
    active = "active"
    paused = "paused" # legacy lmao
    not_enough_balance = "not_enough_balance"

    provisioning = "provisioning"
    inactive = "inactive"          # external “deactivate”
    updating = "updating"
    deleting = "deleting"
    error = "error"
    unknown = "unknown"


from enum import Enum

class KBDataType(str, Enum):
    document = "document"
    video = "video"

class KBEntryStatus(str, Enum):
    in_progress = "in_progress"
    done = "done"
    timeout = "timeout"
    failed = "failed"

# keep this set modest; add more later with a simple migration
class KBLangHint(str, Enum):
    ru = "ru"
    en = "en"
    uk = "uk"
    tr = "tr"
    de = "de"
    fr = "fr"
    es = "es"
    it = "it"
    pt = "pt"
    pl = "pl"
    kk = "kk"
    uz = "uz"
    az = "az"
    ka = "ka"
    ro = "ro"
    nl = "nl"
    sv = "sv"
    no = "no"
    da = "da"
    fi = "fi"
    cs = "cs"
    sk = "sk"
    bg = "bg"
    sr = "sr"
    hr = "hr"
    sl = "sl"
    et = "et"
    lt = "lt"
    lv = "lv"
    el = "el"
    he = "he"
    ar = "ar"
    fa = "fa"
    hi = "hi"
    ur = "ur"
    bn = "bn"
    ta = "ta"
    te = "te"
    ml = "ml"
    id = "id"
    ms = "ms"
    th = "th"
    vi = "vi"
    zh = "zh"
    ja = "ja"
    ko = "ko"
