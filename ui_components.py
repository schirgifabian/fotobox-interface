# ui_components.py

import streamlit as st
from sheets_helpers import get_data_event, get_spreadsheet
from status_logic import HEARTBEAT_WARN_MINUTES


CUSTOM_CSS = """
<style>
.settings-wrapper {
  margin-top: 0.75rem;
}

/* generische Karten-Optik (für Device-Cards) */
.control-card {
  border-radius: 16px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #ffffff, #f9fafb);
  border: 1px solid #e5e7eb;
  box-shadow: 0 18px 45px rgba(15,23,42,0.08);
  margin-bottom: 12px;
}

/* kleine Überschrift über der Karte */
.control-header-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: .08em;
  color:#9ca3af;
  margin-bottom: 2px;
}

/* Hauptzeile mit Icon + Text */
.control-headline {
  font-size: 1.05rem;
  font-weight: 600;
  color:#111827;
  display:flex;
  align-items:center;
  gap: 0.4rem;
  margin-bottom: 6px;
}

/* Status-Badge */
.status-pill {
  margin-top: 4px;
  padding: 4px 10px;
  border-radius:999px;
  font-size: 0.7rem;
  font-weight:600;
  display:inline-flex;
  align-items:center;
  gap:4px;
}
.status-pill--ok {
  background:#dcfce7;
  color:#166534;
}
.status-pill--muted {
  background:#e5e7eb;
  color:#374151;
}
.status-pill--warn {
  background:#fef3c7;
  color:#92400e;
}

/* Zusatzinfos unten */
.control-meta {
  margin-top: 6px;
  font-size: 0.7rem;
  color:#9ca3af;
}

/* rechte Spalte – wir brauchen nur ein sauberes Layout für das Radio */
.segment-wrapper {
  display:flex;
  justify-content:flex-end;
  align-items:center;
}

/* horizontales Radio etwas kompakter */
.control-card .stRadio > div {
  padding-top: 0;
}

/* ----------------------------------------------------
   Admin-Karte
   ---------------------------------------------------- */
.admin-card {
  border-radius:18px;
  border:1px solid #e5e7eb;
  background:#ffffff;
  box-shadow:0 12px 30px rgba(15,23,42,0.05);
  padding:18px 20px 20px 20px;
  margin-bottom:20px;
}

.admin-card-header {
  display:flex;
  justify-content:space-between;
  align-items:baseline;
  margin-bottom:14px;
}

.admin-card-title {
  font-size:16px;
  font-weight:600;
  color:#111827;
}

.admin-card-subtitle {
  font-size:12px;
  color:#9ca3af;
}

.admin-section-title {
  font-size:15px;
  font-weight:600;
  color:#111827;
  margin-bottom:6px;
}

.admin-label-pill {
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.14em;
  color:#9ca3af;
  margin-top:10px;
  margin-bottom:4px;
}

.admin-spacer-xs {
  height:4px;
}

.admin-spacer-sm {
  height:8px;
}
</style>
"""


def inject_custom_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_toggle_card(
    section_title: str,
    description: str,
    state: str,
    title_on: str,
    title_off: str,
    title_unknown: str,
    badge_prefix: str,
    icon_on: str,
    icon_off: str,
    icon_unknown: str,
    btn_left_label: str,
    btn_right_label: str,
    btn_left_key: str,
    btn_right_key: str,
):
    """
    Zeichnet eine Status-Karte mit zwei Buttons (links/rechts).
    Gibt (clicked_left, clicked_right) zurück.
    state: "on" | "off" | "unknown"
    """
    if state == "on":
        bg = "#ecfdf3"
        border = "#bbf7d0"
        icon = icon_on
        title_text = title_on
        badge = f"{badge_prefix}: on"
    elif state == "off":
        bg = "#f9fafb"
        border = "#e5e7eb"
        icon = icon_off
        title_text = title_off
        badge = f"{badge_prefix}: off"
    else:
        bg = "#fffbeb"
        border = "#fed7aa"
        icon = icon_unknown
        title_text = title_unknown
        badge = f"{badge_prefix}: unbekannt"

    container = st.container()
    with container:
        st.markdown(
            f"""
            <div style="
                border-radius:18px;
                border:1px solid {border};
                padding:16px 18px;
                background:{bg};
                display:flex;
                flex-direction:row;
                justify-content:space-between;
                gap:18px;
            ">
                <div style="flex:1;">
                    <div style="font-size:11px; text-transform:uppercase;
                                letter-spacing:.16em; color:#9ca3af; margin-bottom:4px;">
                        {section_title}
                    </div>
                    <div style="font-size:18px; font-weight:600; color:#111827;
                                display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                        <span>{icon}</span>
                        <span>{title_text}</span>
                    </div>
                    <div style="
                        display:inline-flex;
                        align-items:center;
                        padding:3px 10px;
                        border-radius:999px;
                        background:rgba(0,0,0,0.04);
                        font-size:11px;
                        color:#4b5563;
                        margin-bottom:6px;
                    ">
                        {badge}
                    </div>
                    <div style="font-size:12px; color:#6b7280;">
                        {description}
                    </div>
                </div>
                <div style="flex:0 0 180px; display:flex; flex-direction:column; gap:6px;">
                    <div style="font-size:11px; text-transform:uppercase;
                                letter-spacing:.12em; color:#9ca3af; margin-bottom:2px;">
                        Steuerung
                    </div>
            """,
            unsafe_allow_html=True,
        )

        c_left, c_right = st.columns(2)
        with c_left:
            click_left = st.button(
                btn_left_label, key=btn_left_key, use_container_width=True
            )
        with c_right:
            click_right = st.button(
                btn_right_label, key=btn_right_key, use_container_width=True
            )

        st.markdown(
            """
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    """
    Zeigt einen groben Überblick über alle konfigurierten Fotoboxen.
    Nutzt nur die letzte Zeile aus der jeweiligen Tabelle.
    """
    st.subheader("Alle Fotoboxen")

    printers_secrets = st.secrets.get("printers", {})
    cols = st.columns(max(1, min(3, len(PRINTERS))))

    idx = 0
    for name, cfg in PRINTERS.items():
        sheet_id = printers_secrets.get(cfg["key"], {}).get("sheet_id")
        if not sheet_id:
            continue

        try:
            df = get_data_event(sheet_id)
            if df.empty:
                last_ts = "–"
                raw_status = "keine Daten"
                media_raw = None
            else:
                last = df.iloc[-1]
                last_ts = str(last.get("Timestamp", ""))
                raw_status = str(last.get("Status", ""))
                try:
                    media_raw = int(last.get("MediaRemaining", 0)) * cfg.get(
                        "media_factor", 1
                    )
                except Exception:
                    media_raw = None
        except Exception:
            last_ts = "Fehler"
            raw_status = "–"
            media_raw = None

        with cols[idx]:
            st.markdown(
                f"""
                <div style="
                    border-radius:14px;
                    border:1px solid #e5e7eb;
                    padding:10px 12px;
                    background:#f9fafb;
                    font-size:12px;
                    margin-bottom:10px;
                ">
                    <div style="font-weight:600; margin-bottom:4px;">
                        {name}
                    </div>
                    <div style="color:#6b7280; margin-bottom:2px;">
                        Letztes Signal: {last_ts}
                    </div>
                    <div style="color:#6b7280; margin-bottom:2px;">
                        Status: {raw_status}
                    </div>
                    <div style="color:#6b7280;">
                        Verbleibende Drucke: {media_raw if media_raw is not None else '–'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        idx = (idx + 1) % len(cols)


def render_health_overview(aqara_enabled: bool, dsr_enabled: bool):
    items = []

    # Google Sheets
    sheets_ok = False
    try:
        sheet_id_local = st.session_state.get("sheet_id")
        if sheet_id_local:
            _ = get_spreadsheet(sheet_id_local)
            sheets_ok = True
    except Exception:
        sheets_ok = False
    items.append(("Google Sheets", sheets_ok, "Verbindung zur Log-Tabelle"))

    # ntfy
    ntfy_ok = bool(st.session_state.get("ntfy_topic")) and st.session_state.get(
        "ntfy_active", False
    )
    items.append(("ntfy Push", ntfy_ok, "Benachrichtigungen für Probleme"))

    # Aqara
    items.append(("Aqara", aqara_enabled, "Steckdose der Fotobox"))

    # dsrBooth
    items.append(("dsrBooth", dsr_enabled, "Lockscreen-Steuerung"))

    st.markdown("#### Systemstatus")

    cols = st.columns(len(items))
    for col, (name, ok, desc) in zip(cols, items):
        emoji = "✅" if ok else "⚠️"
        col.markdown(
            f"""
            <div style="
                border-radius:12px;
                border:1px solid #e5e7eb;
                padding:8px 10px;
                background:#f9fafb;
                font-size:12px;
                margin-bottom:6px;
            ">
                <div style="font-weight:600; margin-bottom:2px;">
                    {emoji} {name}
                </div>
                <div style="color:#6b7280; font-size:11px;">
                    {desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_status_help(warning_threshold: int):
    with st.expander("ℹ️ Hilfe zu Status & Geräten"):
        st.markdown(
            f"""
**Druckerstatus**

- `✅ Bereit`  
  Drucker ist verbunden und meldet keinen Fehler.

- `⚠️ Papier fast leer`  
  Weniger als **{warning_threshold}** verbleibende Drucke laut Zähler.

- `⚠️ Deckel offen`  
  Der Druckerdeckel ist nicht geschlossen – bitte Deckel prüfen und erneut testen.

- `⏳ Druckkopf kühlt ab…`  
  Der Drucker pausiert kurz, weil der Kopf zu heiß ist. In der Regel reicht es, kurz zu warten.

- `⚠️ Keine aktuellen Daten`  
  Seit mehr als **{HEARTBEAT_WARN_MINUTES}** Minuten ist kein neuer Eintrag vom Fotobox-Skript eingegangen.  
  → Prüfen: Fotobox-PC an? Script läuft? Internet/Google Sheets erreichbar?

- `🔴 STÖRUNG`  
  Harte Fehler wie „paper end“, „ribbon end“, „paper jam“, „data error“ usw.  
  → Papier/Rolle prüfen, Drucker-Display checken, ggf. Papier neu einlegen.

---

**Geräte-Steuerung**

- **Aqara Steckdose Fotobox**  
  Schaltet die Stromversorgung der Fotobox komplett ein/aus.  
  `Ein` = Fotobox bekommt Strom, `Aus` = Fotobox stromlos.

- **dsrBooth – Gästelockscreen**  
  `Sperren` aktiviert den Gästelockscreen (Gäste können keine Fotos starten).  
  `Freigeben` deaktiviert ihn.  
  Der angezeigte Status basiert nur auf der *letzten gesendeten Aktion*, nicht auf einem echten Status-Request.
            """
        )
