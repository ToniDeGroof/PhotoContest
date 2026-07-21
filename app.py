import streamlit as st
from openai import OpenAI
import base64
import io
from PIL import Image

# Pagina-instellingen
st.set_page_config(page_title="F-Art Fotobespreking", page_icon="📷", layout="centered")
# Verberg de zijbalk en startknoppen tijdens het afdrukken/PDF opslaan
st.markdown("""
    <style>
    @media print {
        /* Verberg de gehele zijbalk (met de API key) */
        [data-testid="stSidebar"] {
            display: none !important;
        }
        /* Verberg de startknop en uploaders */
        button[kind="primary"], .stFileUploader {
            display: none !important;
        }
        /* Verberg de Streamlit header en footer */
        header, footer {
            display: none !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# 1. Titel
st.title("📷 F-Art Fotobespreking")

# Zijbalk voor OpenAI API Key
api_key = st.sidebar.text_input("OpenAI API Key:", value="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", type="password")

# 2. Veld om een foto klaar te zetten (ondersteunt ook slepen / drag-and-drop)
st.subheader("1. Foto selecteren")
uploaded_file = st.file_uploader(
    "Sleep je foto hiernaartoe of klik op bladeren...", 
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Klaargezette foto", use_container_width=True)

# 3. Onzichtbare uitgebreide prompt (Systeemprompt / Verborgen basis)
SYSTEM_PROMPT = """
Acteer als een gerespecteerd fotografiecriticus en juryvoorzitter bij fototentoonstellingen.  Ik ga je een foto laten zien. Geef me een uitgebreide, diepgaande bespreking waarin je de volgende aspecten behandelt: 
Vermijd oppervlakkige complimenten en focus op een scherpe, academische en artistieke analyse. Benoem niet alleen wat goed is maar zeker ook wat fout is
1. Visuele en Technische Analyse:
- Compositie en Dynamiek: "Analyseer de compositie van deze foto. Hoe sturen de lijnen, de balans (of het gebrek daaraan) en de kadrering de blik van de kijker? Is er sprake van een bewuste visuele spanning?"
- Licht en Schaduw: "Hoe functioneert het licht in dit beeld? Bespreek de kwaliteit van het licht (hard, zacht, diffuus), de richting, en hoe de schaduwen bijdragen aan de diepte en de sfeer van de foto."
- Technisch Meesterschap: "Wat kun je afleiden over de technische keuzes van de fotograaf? Denk aan scherptediepte (diafragma), bewegingsonscherpte of juist bevriezing (sluitertijd), en de textuur/korrel. Hoe versterken deze keuzes het narratief?"
- Wat is het kleurpalet (complementair, analoog, cinematografisch) en welke emotionele lading dekt dit? 
2. Context en Concept (De Ziel)
- Het Narratief: "Welk verhaal of welk psychologisch moment wordt hier gevangen? Is het een documentair moment (de 'decisive moment' van Cartier-Bresson) of voelt het geregisseerd en conceptueel?"
- Historische en Artistieke Context: "Aan welke historische stroming binnen de fotografie doet dit werk denken.  Welke invloeden van andere fotografen of schilders zie je erin terug?"
- De Onzichtbare Fotograaf: "Wat vertelt het standpunt (vogelperspectief, kikvorsperspectief, ooghoogte) over de relatie tussen de fotograaf en het onderwerp? Is de fotograaf een afstandelijke observator of een intieme deelnemer?"
3. Emotie, Curatie en Marktwaarde
- Emotionele Resonantie: "Welk onbestemd gevoel of welke subtekst roept deze foto op? Waarom blijft dit beeld hangen bij een kijker en wat maakt het universeel?"
- Dit beeld maakt deel uit van een grotere serie, welke rol kan het dan spelen? Werkt het als een krachtig openingsbeeld, een rustpunt, of de climax van een verhaal?"
- De 'Muur-test' (Marketability): "Beoordeel de esthetische en conceptuele duurzaamheid van dit werk. Is dit een foto die standalone overeind blijft in een museale of private collectie, en waarom?"
4. En tot slot:
Geef de foto een score tussen 1 en 100 volgens de sterkte in de volgende 5 categorieën met de bijhorende gewichtsfactor:
Compositie en beeldopbouw 25%
Technische beheersing: 10%
Licht, kleur en tonaliteit: 20%
Visuele en emotionele impact, sfeer: 25%
Verhaal, concept, onderwerp en originaliteit: 20%
"""

# 4. Veld 'Toelichting' (Zichtbaar voor de gebruiker)
st.subheader("2. Extra toelichting")
user_toelichting = st.text_area(
    "Geef hier eventuele extra context of specifieke vragen mee (optioneel):",
    placeholder="Bijv. Deze foto is genomen bij zonsondergang op F/2.8. Ik wil graag weten of de compositie klopt...",
    height=100
)

# Functie om de foto te optimaliseren en om te zetten naar Base64
def prepare_image(pil_image):
    img = pil_image.convert("RGB")
    # Maximaliseer op 1280px voor bliksemsnelle verzending en lage kosten
    img.thumbnail((1280, 1280))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# 5. Startknop & Verwerking
st.subheader("3. Analyse starten")

if st.button("🚀 Start Bespreking", type="primary", use_container_width=True):
    if not api_key:
        st.error("👈 Vul eerst je OpenAI API Key in de zijbalk in!")
    elif uploaded_file is None:
        st.error("Zet eerst een foto klaar!")
    else:
        with st.spinner("⚡ Foto wordt geanalyseerd via OpenAI (gpt-4o-mini)..."):
            try:
                # Client initialiseren met de OpenAI sleutel
                client = OpenAI(api_key=api_key)

                # Afbeelding verkleinen en omzetten naar base64
                base64_image = prepare_image(image)

                # De verborgen prompt en de extra toelichting samenvoegen
                final_prompt = SYSTEM_PROMPT
                if user_toelichting.strip():
                    final_prompt += f"\n\nExtra toelichting van de fotograaf:\n{user_toelichting.strip()}"

                # Aanroep naar gpt-4o-mini
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": final_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=3000
                )

                # Resultaat tonen op het scherm
                st.markdown("---")
                st.subheader("📝 Fotobespreking Resultaat")
                st.write(response.choices[0].message.content)

            except Exception as e:
                st.error(f"Er is een fout ingetreden: {e}")