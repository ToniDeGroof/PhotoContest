import base64
import io
import os
import re
import tempfile
from openai import OpenAI
from fpdf import FPDF
from PIL import Image
import streamlit as st

# ---------------------------------------------------------
# 1. ZIJBALLIK: API-key veilig opvragen aan de gebruiker
# ---------------------------------------------------------
st.sidebar.title("Instellingen")
user_api_key = st.sidebar.text_input(
    "Vul hier je OpenAI API-key in:", 
    type="password", 
    help="Je vindt je sleutel op platform.openai.com"
)

# Controleer of de gebruiker de sleutel heeft ingevuld
if not user_api_key:
    st.info("👈 Voer eerst je OpenAI API-key in aan de linkerkant om de app te starten.")
    st.stop()  # De app stopt hier netjes totdat er een sleutel is ingevuld

# 2. Start de OpenAI client met de ingevoerde sleutel
client = OpenAI(api_key=user_api_key)

if "huidig_scherm" not in st.session_state:
    st.session_state["huidig_scherm"] = "HOME"


# =====================================================================
# 1. PAGINA CONFIGURATIE - CSS - PDF ==================================
# =====================================================================


st.set_page_config(
    page_title="F-Art Fotobespreking", page_icon="📷", layout="centered"
)

st.markdown(
    """
    <style>
    /* CSS voor Schermweergave */
    .stImage img, img {
        max-width: 12cm !important;
        max-height: 12cm !important;
        width: auto !important;
        height: auto !important;
        object-fit: contain !important;
        display: block !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* CSS voor Afdrukken / PDF op A4 */
    @media print {
        [data-testid="stSidebar"],
        header,
        footer,
        .stButton,
        .stFileUploader,
        .stTextArea,
        .stSelectbox,
        .stRadio,
        [data-testid="stHeader"],
        hr,
        .stSubheader, 
        h2,
        h1 {
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        @page {
            size: A4 portrait;
            margin: 0.8cm !important;
        }

        .main .block-container {
            max-width: 100% !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
            margin-top: 0 !important;
        }

        .evaluatie-blok ~ .evaluatie-blok {
            page-break-before: always !important;
            break-before: page !important;
        }

        .evaluatie-blok {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }

        .evaluatie-blok h3 {
            display: block !important;
            font-size: 14pt !important;
            margin-top: 0 !important;
            margin-bottom: 0.2cm !important;
            page-break-after: avoid !important;
        }

        img {
            max-width: 8.5cm !important;
            max-height: 8.5cm !important;
            width: auto !important;
            height: auto !important;
            display: block !important;
            margin-top: 0 !important;
            margin-bottom: 0.3cm !important;
            page-break-before: avoid !important;
            page-break-after: avoid !important;
        }

        h4, strong, b {
            display: block !important;
            font-weight: bold !important;
            margin-top: 0.2cm !important;
            margin-bottom: 0.05cm !important;
            page-break-after: avoid !important;
        }

        p, li, div {
            font-size: 8.5pt !important;
            line-height: 1.15 !important;
            margin-top: 0 !important;
            margin-bottom: 0.1cm !important;
            color: #000000 !important;
        }

        body {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
    }
    </style>
""",
    unsafe_allow_html=True,
)

# =====================================================================
# 2. CONSTANTEN & INSTELLINGEN
# =====================================================================
GENRES = [
    "Algemeen & Vrij werk",
    "Portret & Mensfotografie",
    "Landschap & Natuur",
    "Zwart/wit Fotografie",
    "Straatfotografie",
    "Macro & Detailfotografie",
    "Architectuur & Interieur",
    "Creatief & Conceptueel",
    "Documentair & Reportage",
    "Stilleven",
    "Studio",
    "Nacht & Low-Light",
]

# Geheugen / Navigatiestatus initialiseren
if "huidig_scherm" not in st.session_state:
    st.session_state["huidig_scherm"] = "HOME"

# OpenAI API Client initialiseren
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input(
        "OpenAI API Key", type="password", help="Voer je OpenAI API key in"
    )

if not api_key:
    st.info("Voer a.u.b. een OpenAI API Key in om de app te gebruiken.")
    st.stop()

client = OpenAI(api_key=api_key)


# =====================================================================
# 3. HULPFUNCTIES (SCORES & PDF GENERATIE)
# =====================================================================
def geef_beoordeling_details(score):
    """Zet een score van 0-100 om naar sterren (0-5) en een interpretatietekst."""
    if score >= 90:
        return (
            "⭐⭐⭐⭐⭐",
            "Uitzonderlijk niveau. Onberispelijke techniek, ijzersterke compositie en een unieke artistieke visie. De foto heeft zeggingskracht en overstijgt het gemiddelde clubniveau ruimschoots.",
        )
    elif score >= 80:
        return (
            "⭐⭐⭐⭐",
            "Zeer hoog niveau. Hoge technische beheersing en een doordachte beeldopbouw. Een beeld dat direct aanspreekt en waarin het vakmanschap duidelijk zichtbaar is.",
        )
    elif score >= 70:
        return (
            "⭐⭐⭐",
            "Goede clubkwaliteit. Het beeld is technisch goed verzorgd en compositorisch geslaagd. De intentie van de fotograaf is duidelijk zichtbaar. Met een kleine verfijning in afwerking, belichting of uitsnede kan dit beeld doorgroeien naar topniveau.",
        )
    elif score >= 60:
        return (
            "⭐⭐",
            "Degelijk basiswerk. Het idee is goed en de foto is technisch acceptabel, maar mist wat spanning, scherpte of doordachte compositie om echt te pakken.",
        )
    elif score >= 50:
        return (
            "⭐",
            "Aandachtspunten aanwezig. Het potentieel is er, maar technische fouten (zoals misse scherpte, verkeerde belichting of slordige afwerking) leiden af van de inhoud.",
        )
    else:
        return (
            "⚪ (0 sterren)",
            "Beginnersstadium of grote technische gebreken. Belangrijke basiselementen (scherpte, belichting, compositie) schieten tekort. Het beeld heeft een grondige herziening nodig in opname of nabewerking om tot zijn recht te komen.",
        )


def maak_veilige_tekst(tekst):
    """Vervangt speciale Unicode-tekens door FPDF-veilige karakters."""
    if not tekst:
        return ""

    vervangingen = {
        "×": "x",
        "÷": "/",
        "…": "...",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201C": '"',
        "\u201D": '"',
        "•": "-",
        "é": "e",
        "ë": "e",
        "è": "e",
    }

    for oud, nieuw in vervangingen.items():
        tekst = tekst.replace(oud, nieuw)

    return tekst.encode("latin-1", "replace").decode("latin-1")


def maak_pdf_van_verslag(tekst, titel, bytes_image, score=70):
    """Genereert een downloadbaar PDF-juryrapport met afbeelding en opgemaakte tekst."""
    sterren, interpretatie = geef_beoordeling_details(score)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 1. Titel
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, maak_veilige_tekst(titel), ln=True, align="C")
    pdf.ln(2)

    # 2. Score & Interpretatie
    schone_sterren = sterren.replace("★", "*").replace("☆", "")
    pdf.set_font("Arial", "B", 13)
    pdf.cell(
        0,
        8,
        maak_veilige_tekst(
            f"Eindscore: {score}/100 - Beoordeling: {schone_sterren}"
        ),
        ln=True,
        align="C",
    )

    pdf.set_font("Arial", "I", 10)
    pdf.cell(
        0,
        6,
        maak_veilige_tekst(f"Interpretatie: {interpretatie}"),
        ln=True,
        align="C",
    )
    pdf.ln(5)

    # 3. Afbeelding invoegen
    if bytes_image:
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg"
            ) as tmp_file:
                tmp_file.write(bytes_image)
                tmp_path = tmp_file.name

            pdf.image(tmp_path, x=45, w=120)
            pdf.ln(8)
        except Exception as e:
            print(
                f"Waarschuwing: Afbeelding kon niet in PDF geplaatst worden: {e}"
            )
        finally:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # 4. Inhoudsopmaak
    regels = tekst.split("\n")

    for regel in regels:
        regel = regel.strip()
        if not regel:
            pdf.ln(3)
            continue

        safe_regel = maak_veilige_tekst(regel)

        # Kopjes
        if safe_regel.startswith("#") or (
            safe_regel.startswith("**") and safe_regel.endswith("**")
        ):
            schone_regel = (
                safe_regel.replace("#", "").replace("**", "").strip()
            )
            pdf.set_font("Arial", "B", 11)
            pdf.ln(2)
            pdf.multi_cell(0, 6, schone_regel)
            pdf.set_font("Arial", "", 10)

        # Opsommingen
        elif safe_regel.startswith("- ") or safe_regel.startswith("* "):
            schone_regel = (
                "- " + safe_regel[2:].replace("**", "").replace("*", "")
            )
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 5, "   " + schone_regel)

        # Broodtekst
        else:
            schone_regel = safe_regel.replace("**", "").replace("*", "")
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 5, schone_regel)

    bestandspad = "jury_rapport_temp.pdf"
    pdf.output(bestandspad)
    return bestandspad

# =====================================================================
# 4. SCHERM: HOME - STARTSCHERM =======================================
# =====================================================================
if st.session_state["huidig_scherm"] == "HOME":
    st.title("F-Art Fotoclub - AI Beoordeling")

    st.markdown("---")

    # CSS om de pictogrammen op formaat te houden en knoptekst netjes te stijlen
    st.markdown(
        """
        <style>
        div[data-testid="stColumn"] img {
            max-height: 250px !important;
            width: auto !important;
            margin: 0 auto !important;
            display: block !important;
            object-fit: contain !important;
        }
        /* Zorgt ervoor dat meerregelige teksten in knoppen goed gecentreerd staan */
        div[data-testid="stColumn"] button {
            white-space: pre-wrap !important;
            height: auto !important;
            padding-top: 12px !important;
            padding-bottom: 12px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Info-veld bovenaan het startscherm
    st.info(
        """ℹ️ **Hoe werkt de AI Fotoclub Beoordeling?**

Kies uit een van de drie onderstaande opties om direct aan de slag te gaan:\n\n
• **Optie 1 - Foto's:** Geeft voor 1 tot max 4 foto's een uitgebreide beoordeling op compositie, techniek, sfeer en emotie, licht en kleur, ....\n\n
• **Optie 2 - Reeksen:** Upload 4 tot 25 foto's en laat de curator je helpen met het selecteren van het gewenste aantal beelden, laat schrappen en bepaal een volgorde voor een expositie of fotoboek.\n\n
• **Optie 3 - Curator:** Upload een serie van 4 tot 25 foto's voor een  grondige analyse op rode draad, verhaallijn en samenhang."""
    )

    st.markdown("---")

    # Drie strakke kolommen
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            "<h3 style='text-align: center;'>Foto's</h3>",
            unsafe_allow_html=True,
        )
        st.image("foto-1.jpg")
        if st.button(
            "Optie 1\n1 tot 4 foto's\nGrondige evaluatie\nBeeld per beeld",
            key="btn_home_1",
            use_container_width=True,
            type="primary",
        ):
            st.session_state["huidig_scherm"] = "SCHERM_A"
            st.rerun()

    with col3:
        st.markdown(
            "<h3 style='text-align: center;'>Curator</h3>",
            unsafe_allow_html=True,
        )
        st.image("foto-2.jpg")
        if st.button(
            "Optie 3\n Reeks van 4 tot 25 foto's\nSelecteert en schrapt\Voor boek en expo",
            key="btn_home_2",
            use_container_width=True,
            type="primary",
        ):
            st.session_state["huidig_scherm"] = "SCHERM_B1"
            st.rerun()

    with col2:
        st.markdown(
            "<h3 style='text-align: center;'>Reeksen</h3>",
            unsafe_allow_html=True,
        )
        st.image("foto-3.jpg")
        if st.button(
            "Optie 2\nReeks van 4 tot 25 foto's\nBeoordeelt samenhang\nen verhaal",
            key="btn_home_3",
            use_container_width=True,
            type="primary",
        ):
            st.session_state["huidig_scherm"] = "SCHERM_B2"
            st.rerun()

    # Dwing Streamlit om hier te stoppen
    st.stop()

# =====================================================================
# 5. SCHERM: CURATOR-SELECTIE - 4 TOT 25 FOTO'S =======================
# =====================================================================
if st.session_state["huidig_scherm"] == "SCHERM_B1":
    st.title("F-Art Fotoclub - Curator")
    if st.button("Terug naar Startscherm", icon="⬅️", type="secondary"):
        st.session_state["huidig_scherm"] = "HOME"
        st.rerun()

    st.markdown("---")

    # CSS om het overlapping-probleem definitief op te lossen met vaste thumbnail-afmetingen
    st.markdown(
        """
        <style>
        .stImage img {
            max-height: 100px !important;
            width: auto !important;
            object-fit: contain;
            margin: 0 auto;
            display: block;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Info-veld voor instructies en fotovoorwaarden
    st.info(
        """ℹ️ **Optie 2: Curator-Selectie & Schrappen (4 tot 25 foto's)**

Gebruik deze optie als je twijfelt tussen meerdere beelden of hulp zoekt bij het schrappen voor een expositie, boek of wedstrijd.

**Richtlijnen:**
• Upload 4 tot 25 foto's (JPG of PNG).
• Aanbevolen resolutie: max. 2000px aan de langste zijde (max 2MB per bestand).
• Geef aan hoeveel beelden er uiteindelijk over moeten blijven."""
    )

    st.subheader("Selectie-Hulp: Maak de sterkste selectie uit je beelden")
    st.write(
        "Upload je foto's. De AI-curator helpt je met schrappen, selecteren en rangschikken tot de meest krachtige set."
    )

    uploaded_files_b1 = st.file_uploader(
        "Kies 4 tot 25 afbeeldingen...",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="uploader_b1",
    )

    if uploaded_files_b1:
        aantal = len(uploaded_files_b1)
        if aantal < 4:
            st.warning(
                f"⚠️ Je hebt {aantal} foto('s) gekozen. Voor een curator-selectie zijn minimaal 4 foto's nodig."
            )
        elif aantal > 25:
            st.error(
                f"⚠️ Je hebt {aantal} foto's gekozen. Het maximum is 25 foto's per sessie."
            )
        else:
            st.success(
                f"✅ {aantal} foto's geladen en klaar voor curator-analyse."
            )

            # --- COMPACT CONTACTSHEET RASTER ---
            st.markdown("### Geüploade foto's")
            col_per_rij = 6
            for i in range(0, aantal, col_per_rij):
                rij_files = uploaded_files_b1[i : i + col_per_rij]
                cols = st.columns(col_per_rij)

                for idx, file in enumerate(rij_files):
                    with cols[idx]:
                        full_name = file.name
                        if len(full_name) > 12:
                            short_name = full_name[:5] + "..." + full_name[-3:]
                        else:
                            short_name = full_name

                        st.image(file)
                        st.caption(
                            f"**{short_name}**",
                            help=f"Volledige bestandsnaam: {full_name}",
                        )

            st.markdown("---")
            st.subheader("Instructies voor de Curator")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                einddoel = st.selectbox(
                    "Waarvoor is de selectie bedoeld?",
                    options=[
                        "Expositie / Galerij",
                        "Clubfotowedstrijd / Fotobond",
                        "Fotoboek / Portfolio",
                        "Social Media / Serie",
                        "Persoonlijke archivering",
                    ],
                )

                gewenst_aantal = st.number_input(
                    "Hoeveel foto's moeten er overblijven?",
                    min_value=1,
                    max_value=max(1, aantal - 1),
                    value=min(5, max(1, aantal - 1)),
                    step=1,
                    help="Kies het exacte aantal beelden dat over moet blijven.",
                )

            with col_c2:
                hoofdfocus = st.selectbox(
                    "Wat is de belangrijkste eis voor de selectie?",
                    options=[
                        "Maximale visuele afwisseling & variatie",
                        "Sterkste inhoudelijke/narratieve samenhang",
                        "Technisch de allerbeste foto's",
                        "Meest unieke / artistieke beelden",
                    ],
                )
                extra_toelichting = st.text_area(
                    "Toelichting of specifieke twijfels (optioneel):",
                    placeholder="Bijv. 'Twijfel tussen foto X en Y' of 'Wil maximaal 1 portret opnemen'...",
                )

            if st.button(
                "Start Curator-Selectie",
                type="primary",
                use_container_width=True,
                key="btn_start_b1",
            ):
                curator_prompt = f"""
Je bent een meedogenloze maar opbouwende fotocurator en galeriehouder. Je taak is om uit een ingezonden set van precies {aantal} foto's de meest krachtige, coherente en impactvolle selectie van {gewenst_aantal} beelden te maken.

Meegegeven doelen:
- Einddoel van de selectie: {einddoel}
- Exact gewenst aantal eindbeelden: {gewenst_aantal}
- Belangrijkste selectiecriterium: {hoofdfocus}
- Extra toelichting fotograaf: {extra_toelichting if extra_toelichting else 'Geen'}

BELANGRIJKE INSTRUCTIE VOOR HET REFEREREN NAAR FOTO'S:
Gebruik bij elke besproken foto ALTIJD de exacte bestandsnaam (bijvoorbeeld: 'eindwerk-24.jpg').

Structureer je rapport verplicht als volgt:

**1. De Geselecteerde Top-Set ({gewenst_aantal} foto's)**
Noem expliciet de gekozen bestandsnamen en onderbouw bij ELKE gekozen foto kort waarom deze de selectie heeft gehaald.

**2. Welke foto's afvallen en waarom**
Geef een lijst van de afgevallen foto's met de exacte bestandsnaam en per foto de heldere reden van afvallen.

**3. Aanbevolen Presentatie / Volgorde**
Geef de ideale volgorde aan (op basis van de bestandsnamen) waarin deze geselecteerde beelden getoond of gehangen moeten worden voor de grootste visuele impact.

**4. Eindoordeel van de Curator**
Korte samenvatting van de kwaliteit van de ingezonden serie en de sterkte van het uiteindelijke resultaat.
"""
                with st.spinner(
                    f"Curator analyseert {aantal} foto's en maakt de beste selectie..."
                ):
                    try:
                        content_array = [{"type": "text", "text": curator_prompt}]

                        for idx, file in enumerate(uploaded_files_b1, start=1):
                            bytes_data = file.getvalue()
                            b64_img = base64.b64encode(bytes_data).decode("utf-8")

                            content_array.append(
                                {
                                    "type": "text",
                                    "text": f"--- FOTO {idx} van {aantal}: Bestandsnaam = '{file.name}' ---",
                                }
                            )
                            content_array.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_img}"
                                    },
                                }
                            )

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": content_array}],
                            max_tokens=4000,
                            temperature=0.7,
                        )

                        st.session_state["curator_resultaat"] = response.choices[
                            0
                        ].message.content
                        st.rerun()

                    except Exception as e:
                        st.error(f"Fout bij het verwerken van de reeks: {e}")

    # Resultaatweergave Curator
    if "curator_resultaat" in st.session_state:
        st.markdown("---")
        st.header("📋 Rapport van de Curator")
        st.markdown(st.session_state["curator_resultaat"])
        if st.button("Nieuwe selectie starten", type="secondary"):
            st.session_state.pop("curator_resultaat", None)
            st.rerun()

    st.stop()


# =====================================================================
# 6. SCHERM: REEKS-ANALYSE - 4 TOT 25 FOTO'S ==========================
# =====================================================================
if st.session_state["huidig_scherm"] == "SCHERM_B2":
    st.title("F-Art Fotoclub - Reeks-Analyse")
    if st.button("Terug naar Startscherm", icon="⬅️", type="secondary"):
        st.session_state["huidig_scherm"] = "HOME"
        st.rerun()

    st.markdown("---")

    # CSS om het overlapping-probleem definitief op te lossen met vaste thumbnail-afmetingen
    st.markdown(
        """
        <style>
        .stImage img {
            max-height: 100px !important;
            width: auto !important;
            object-fit: contain;
            margin: 0 auto;
            display: block;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Info-veld voor instructies en fotovoorwaarden
    st.info(
        """ℹ️ **Optie 3: Serie- & Reeks-Analyse (4 tot 25 foto's)**

Laat een complete serie beoordelen op rode draad, verhaallijn, visueel ritme en de onderlinge samenhang van je portfolio.

**Richtlijnen:**
• Upload 4 tot 25 foto's van een afgeronde serie (JPG of PNG).
• Aanbevolen resolutie: max. 2000px aan de langste zijde (max 2MB per bestand)."""
    )

    st.subheader("Reeks-Analyse: Beoordeel je complete serie of portfolio")
    st.write(
        "Upload 4 tot 25 foto's van een voltooide serie. De AI beoordeelt de samenhang, rode draad, verhaallijn en totale kwaliteit."
    )

    uploaded_files_b2 = st.file_uploader(
        "Kies 4 tot 25 afbeeldingen...",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="uploader_b2",
    )

    if uploaded_files_b2:
        aantal = len(uploaded_files_b2)
        if aantal < 4:
            st.warning(
                f"⚠️ Je hebt {aantal} foto('s) gekozen. Voor een reeks-analyse zijn minimaal 4 foto's nodig."
            )
        elif aantal > 25:
            st.error(
                f"⚠️ Je hebt {aantal} foto's gekozen. Het maximum is 25 foto's per sessie."
            )
        else:
            st.success(f"✅ {aantal} foto's geladen voor de Reeks-Analyse.")

            # --- COMPACT CONTACTSHEET RASTER ---
            st.markdown("### Geüploade foto's")
            col_per_rij = 6
            for i in range(0, aantal, col_per_rij):
                rij_files = uploaded_files_b2[i : i + col_per_rij]
                cols = st.columns(col_per_rij)

                for idx, file in enumerate(rij_files):
                    with cols[idx]:
                        full_name = file.name
                        if len(full_name) > 12:
                            short_name = full_name[:5] + "..." + full_name[-3:]
                        else:
                            short_name = full_name

                        st.image(file)
                        st.caption(
                            f"**{short_name}**",
                            help=f"Volledige bestandsnaam: {full_name}",
                        )

            st.markdown("---")
            st.subheader("Informatie over de Serie")

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                reeks_type = st.selectbox(
                    "Type Reeks:",
                    options=[
                        "Thematische Serie (één onderwerp/stijl)",
                        "Narratieve Reportage (verhaal/volgorde)",
                        "Gevarieerd Portfolio (diverse genres)",
                        "Conceptueel / Fine-Art Project",
                    ],
                )
                genre_reeks = st.selectbox(
                    "Hoofdgenre van de reeks:", options=GENRES
                )

            with col_r2:
                concept_tekst = st.text_area(
                    "Concept / Rode Draad van de serie:",
                    placeholder="Wat bindt deze foto's samen? Wat is de visuele of inhoudelijke gedachte?",
                )

            if st.button(
                "Start Reeks-Analyse",
                type="primary",
                use_container_width=True,
                key="btn_start_b2",
            ):
                reeks_prompt = f"""
Je bent een vooraanstaand fotocriticus en jurylid voor fotoprojecten en exposities. Je beoordeelt een complete reeks van precies {aantal} foto's op onderlinge samenhang, visuele ritmiek, rode draad en totale kwaliteit.

Meegegeven serie-informatie:
- Type Reeks: {reeks_type}
- Hoofdgenre: {genre_reeks}
- Opgegeven concept/rode draad: {concept_tekst if concept_tekst else 'Niet opgegeven'}

BELANGRIJKE INSTRUCTIE VOOR HET REFEREREN NAAR FOTO'S:
Gebruik bij elke besproken foto ALTIJD de exacte bestandsnaam (bijvoorbeeld: 'eindwerk-12.jpg').

Structureer je jury-rapport verplicht met de volgende genummerde kopjes:

**1. Rode Draad & Samenhang**
Analyseer hoe goed de foto's bij elkaar passen. Is er sprake van een eenduidige bewerkingsstijl, lichtgebruik, kleurenpalet of inhoudelijk thema?

**2. Visuele Ritmiek & Opbouw**
Beoordeel de volgorde en het verloop van de serie. Is er variatie in standpunten/kadering (bijv. afwisseling tussen overzicht, medium en detail) of voelt het eentonig?

**3. Sterkste en Zwakste Schakel**
- Noem expliciet welke **bestandsnaam** de sterkste foto in de reeks is en waarom.
- Noem expliciet welke **bestandsnaam** de zwakste foto in de reeks is (die de serie omlaag haalt) en waarom.

**4. Verbeterpunten voor de Serie**
Geef concrete tips met kogelpunten (-) om de serie als geheel te versterken (bijv. volgorde aanpassen, specifieke foto vervangen of nabewerking gelijktrekken).

**5. Serie Eindscore**
Geef een cijfer van 0 tot 100 voor de serie als GEHEEL en onderbouw dit kort.
Eindig verplicht met:
EINDSCORE REEKS: [getal]
"""
                with st.spinner(
                    f"Jury analyseert de serie van {aantal} foto's..."
                ):
                    try:
                        content_array = [{"type": "text", "text": reeks_prompt}]

                        for idx, file in enumerate(uploaded_files_b2, start=1):
                            bytes_data = file.getvalue()
                            b64_img = base64.b64encode(bytes_data).decode("utf-8")

                            content_array.append(
                                {
                                    "type": "text",
                                    "text": f"--- FOTO {idx} van {aantal}: Bestandsnaam = '{file.name}' ---",
                                }
                            )
                            content_array.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_img}"
                                    },
                                }
                            )

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": content_array}],
                            max_tokens=4000,
                            temperature=0.7,
                        )

                        st.session_state["reeks_resultaat"] = response.choices[
                            0
                        ].message.content
                        st.rerun()

                    except Exception as e:
                        st.error(f"Fout bij het verwerken van de reeks: {e}")

    # Resultaatweergave Reeks
    if "reeks_resultaat" in st.session_state:
        st.markdown("---")
        st.header("📋 Jury-Rapport Reeks-Analyse")
        st.markdown(st.session_state["reeks_resultaat"])
        if st.button("Nieuwe reeks-analyse starten", type="secondary"):
            st.session_state.pop("reeks_resultaat", None)
            st.rerun()

    st.stop()

# =====================================================================
# 7. SCHERM: INDIVIDUELE FOTOBEOORDELING - 1 tot 4 foto's =============
# =====================================================================
st.title("📷 F-Art Fotoclub")
if st.button("Terug naar Startscherm", type="secondary"):
    st.session_state["huidig_scherm"] = "HOME"
    st.rerun()

st.markdown("---")

# 7.1 Uploads
uploaded_files = st.file_uploader(
    "Kies 1 tot 4 afbeeldingen...",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.markdown("---")
    st.write(f"**Geselecteerde foto('s) ({len(uploaded_files)}):**")

    for idx, file in enumerate(uploaded_files):
        st.image(file, caption=f"Foto {idx+1}", width=500)

    st.markdown("---")
    st.subheader("Informatie voor de Jury")

    col1, col2 = st.columns(2)

    with col1:
        gekozen_genre = st.selectbox(
            "Selecteer het genre van de foto('s):", options=GENRES
        )

    with col2:
        kleurtype = st.radio(
            "Kleurtype:",
            options=["Kleur", "Zwart-wit", "Monochroom / Toned"],
            horizontal=True,
        )

    user_intentie = st.text_area(
        "Intentie van de fotograaf:",
        placeholder="Wat wilde je met deze foto bereiken, uitstralen of overbrengen?",
    )

    user_context = st.text_area(
        "Context & Omstandigheden:",
        placeholder="Onder welke omstandigheden is de foto gemaakt? (locatie, tijdstip, lichtomstandigheden, e.d.)",
    )

    techniek_info = st.text_area(
        "Technische keuzes & Nabewerking (optioneel):",
        placeholder="Bijv. ISO, sluitertijd, diafragma, uitsnede, specifieke bewerkingen...",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    str_intentie = user_intentie if user_intentie else "Niet opgegeven"
    str_context = user_context if user_context else "Niet opgegeven"
    str_techniek = techniek_info if techniek_info else "Niet opgegeven"

    # 7.2 Verwerking via AI
    if st.button(
        "Start Beoordeling",
        type="primary",
        use_container_width=True,
        key="btn_start_main",
    ):

        superprompt = f"""
Je bent een ervaren fotografierecensent met een professionele, analytische en evenwichtige stijl. Je beoordeelt fotografische reeksen grondig, eerlijk en uiterst gedetailleerd. Je benoemt wat functioneel werkt en wat niet werkt, en je geeft concrete verbeterpunten die fotografen helpen groeien. Je bent niet hard, maar wel duidelijk, analytisch en veeleisend.

Meegegeven metadata:
- Genre: {gekozen_genre}
- Kleurtype: {kleurtype}
- Intentie: {str_intentie}
- Context en omstandigheden: {str_context}
- Technische keuzes en nabewerking: {str_techniek}

Opmerking: Indien metadata niet is opgegeven, beoordeel je uitsluitend op wat visueel waarneembaar is.

INSTRUCTIES VOOR DIEPGANG & LENGTE:
- Bied bij elk onderdeel een uitgebreide, diepgaande analyse. Schrijf geen korte samenvatting of oppervlakkige zinnen.
- Licht elk punt toe met concrete voorbeelden uit het specifieke beeld (locatie in de foto, lichtinval, details, scherptevlak, kleurtinten).

OPMAAKREGELS:
- Gebruik STRIKT de onderstaande 7 genummerde kopjes.
- Maak elk kopje VETGEDRUKT met dubbele asterisks, bijv: **1. Functionele elementen**
- Plaats de inhoud van elk punt ALTIJD op een NIEUWE REGEL onder het kopje.
- Gebruik bij punt 6 KOGELPUNTEN (met een - streepje) voor de verbeterpunten, GEEN cijfers!

Beoordelingsstructuur:

**1. Functionele elementen**
Geef een uitgebreide analyse van welke elementen functioneel werken in het beeld. Bespreek grondig en achtereenvolgens:
- Compositie en visuele structuur (lijnen, balans, regel van derden/gouden snede, rust)
- Licht, kleur en tonaliteit (kwaliteit van het licht, contrast, kleurenharmonie)
- Technische beheersing (scherpte, scherptediepte, ruis, belichting)
- Concept en intentie (wat brengt het beeld over)
- Emotionele impact of wow-factor (sfeer, zeggingskracht)
- Genre-specifieke criteria

**2. Zwakke punten en slordigheden**
Analyseer compositie, lichtval, kleur en tonaliteit, technische beheersing, narratief, sfeer en afwerking. Benoem expliciet en gedetailleerd fouten, storende randelementen, gemiste kansen, inconsistenties, verkeerde keuzes en technische tekortkomingen.

**3. Genre-specifieke beoordeling**
Beoordeel de foto grondig volgens de maatstaven van het gekozen genre ({gekozen_genre}):
- Straatfotografie: timing, context, authenticiteit, beeldelementen
- Portret: lichtvorming op gelaat, oog-scherpte, expressie, huidtinten, pose, achtergrond
- Landschap: lichtkwaliteit, dieptewerking, voorgrond/achtergrond, horizon, schaal
- Architectuur: lijnen, perspectief, geometrie, symmetrie, vervorming
- Macro of detail: scherptediepte, isolatie, detail, ruis
- Fine-art of creatief: conceptuele sterkte, intentie, artistieke coherentie
- Documentair of reportage: eerlijkheid, context, narratief, moment

**4. Intentie- en contextanalyse**
Beoordeel uitgebreid of de foto de opgegeven intentie ({str_intentie}) ondersteunt of ondermijnt. Benoem precies waar de intentie faalt, niet zichtbaar is of inconsistent overkomt.

**5. Technische analyse**
Geef een diepgaande technische beoordeling van scherpte, scherptediepte, belichting (hooglichten en schaduwen), ruis, lenskeuze, kleurbalans, toonwaarden en nabewerking. Benoem technische fouten direct en zonder verzachting.

**6. Directe verbeterpunten**
Geef een lijst met een - streepje voor specifieke, uitvoerbare en gedetailleerde acties om het beeld te verbeteren. Geen algemeenheden, maar exacte instructies zoals:
- Snijd 5 procent van de rechterzijde af om het storende element te verwijderen
- Verlaag de hooglichten in de achtergrond
- Pas de kleurtemperatuur licht aan voor meer coherentie

**7. Scoreberekening**
Geef per categorie een duidelijke deelscore met onderbouwing en bereken daarna de totaalscore.
Gebruik de volgende categorieën en hun verdeelsleutel:
- Compositie en visuele structuur: 25 procent
- Licht, kleur en tonaliteit: 20 procent
- Technische beheersing: 15 procent
- Concept en intentie: 20 procent
- Emotionele impact of wow-factor: 15 procent
- Genre-specifieke criteria: 5 procent

Genre-correctie:
Pas na het berekenen van de totaalscore een correctiefactor toe op basis van het gekozen genre ({gekozen_genre}).

Correctiefactoren:
- Straatfotografie: vermenigvuldig met 1.05
- Documentair en reportage: vermenigvuldig met 1.05
- Creatief en conceptueel: vermenigvuldig met 1.10
- Zwart-wit fotografie: vermenigvuldig met 1.03
- Nacht en low-light: vermenigvuldig met 1.04
- Macro en detailfotografie: vermenigvuldig met 0.97
- Landschap en natuur: vermenigvuldig met 0.95
- Stilleven: vermenigvuldig met 1.00
- Studio: vermenigvuldig met 0.98
- Portret en mensfotografie: vermenigvuldig met 1.00
- Architectuur en interieur: vermenigvuldig met 0.97
- Algemeen of vrij werk: vermenigvuldig met 1.00

Bereken de gecorrigeerde eindscore (totaalscore × correctiefactor) afgerond op een heel getal.

VERPLICHTE LAATSTE REGEL VAN JE ANTWOORD:
Eindig het rapport ALTIJD op de allerlaatste regel met exact deze structuur (vervang [getal] door de berekende score):
EINDSCORE: [getal]
"""

        evaluaties_resultaat = []

        for index, file in enumerate(uploaded_files, start=1):
            with st.spinner(
                f"Foto {index} van {len(uploaded_files)} jureren ({gekozen_genre})..."
            ):
                try:
                    bytes_data = file.getvalue()
                    base64_image = base64.b64encode(bytes_data).decode("utf-8")

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": superprompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        },
                                    },
                                ],
                            }
                        ],
                        max_tokens=4000,
                        temperature=0.7,
                    )

                    rapport_tekst = response.choices[0].message.content

                    # Score uitlezen
                    score_match = re.search(
                        r"EINDSCORE:\s*(\d{1,3})", rapport_tekst, re.IGNORECASE
                    )

                    if score_match:
                        gevonden_score = int(score_match.group(1))
                    else:
                        alle_nummers = re.findall(
                            r"\b([1-9][0-9]?|100)\b", rapport_tekst
                        )
                        gevonden_score = (
                            int(alle_nummers[-1]) if alle_nummers else 50
                        )

                    gevonden_score = max(0, min(100, gevonden_score))

                    evaluaties_resultaat.append(
                        {
                            "bytes": bytes_data,
                            "tekst": rapport_tekst,
                            "genre": gekozen_genre,
                            "score": gevonden_score,
                        }
                    )

                except Exception as e:
                    st.error(
                        f"🚨 Er is een fout ingetreden bij verwerking van foto {index}: {e}"
                    )

        if evaluaties_resultaat:
            st.session_state["evaluaties"] = evaluaties_resultaat
            st.rerun()
        else:
            st.error(
                "Er konden geen evaluaties gegenereerd worden. Controleer je OpenAI API-key of netwerkverbinding."
            )


# =====================================================================
# 8. SCHERM: RESULTATEN WEERGEVEN
# =====================================================================
if "evaluaties" in st.session_state and st.session_state["evaluaties"]:
    st.markdown("---")
    st.header("Resultaten van de Beoordeling")

    if "pdf_ready" not in st.session_state:
        st.session_state["pdf_ready"] = {}

    for index, item in enumerate(st.session_state["evaluaties"], start=1):
        st.subheader(f"Jury-Rapport ({item['genre']}) - Foto {index}")
        st.image(item["bytes"], use_container_width=500)

        score = item.get("score", 50)
        sterren, interpretatie = geef_beoordeling_details(score)

        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Berekende Eindscore", value=f"{score} / 100")
        with col2:
            st.markdown(f"### Beoordeling: {sterren}")

        st.info(f"**Interpretatie:** {interpretatie}")
        st.markdown(item["tekst"])

        # PDF Acties
        if st.button(
            f"Maak PDF voor foto {index}",
            type="primary",
            use_container_width=True,
            key=f"maak_pdf_{index}",
        ):
            pdf_pad = maak_pdf_van_verslag(
                item["tekst"],
                f"Jury-Rapport ({item['genre']}) - Foto {index}",
                item["bytes"],
                score=score,
            )
            if pdf_pad:
                st.session_state["pdf_ready"][index] = pdf_pad
                st.rerun()

        if (
            index in st.session_state["pdf_ready"]
            and st.session_state["pdf_ready"][index]
        ):
            st.markdown("### PDF klaar om te bewaren")
            try:
                with open(st.session_state["pdf_ready"][index], "rb") as f:
                    st.download_button(
                        f"PDF bewaren voor foto {index}",
                        f,
                        file_name=f"jury_rapport_foto_{index}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"bewaar_pdf_{index}",
                    )
            except FileNotFoundError:
                st.error(
                    "Het PDF-bestand kon niet worden gevonden op de schijf."
                )

        st.markdown("---")

    if st.button(
        "Nieuwe beoordeling starten",
        type="secondary",
        use_container_width=True,
        key="btn_herstart",
    ):
        st.session_state.pop("evaluaties", None)
        st.session_state["pdf_ready"] = {}
        st.rerun()