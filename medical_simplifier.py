"""
Medical Jargon and Prescription Simplifier Engine.
Translates complex clinical notes, abbreviations, and doctor prescriptions into plain,
reassuring layperson language, dosage schedules, safety warnings, and speech-ready summaries.
Supports multiple local languages: English (en), Hindi (hi), Bengali (bn), Spanish (es), French (fr).
"""

import re
from typing import Optional, Dict, Any, List

# Latin prescription abbreviations to plain English
RX_ABBREVIATIONS = {
    r"\bpo\b": "by mouth (swallow with water)",
    r"\bbid\b": "twice a day (every 12 hours)",
    r"\btid\b": "3 times a day (morning, afternoon, night)",
    r"\bqid\b": "4 times a day (every 6 hours)",
    r"\bod\b": "once a day",
    r"\bhs\b": "at bedtime",
    r"\bprn\b": "only as needed when symptoms appear",
    r"\bac\b": "before meals (on an empty stomach)",
    r"\bpc\b": "after meals (with or after food)",
    r"\bstat\b": "immediately / right now",
    r"\biv\b": "into the vein (intravenous injection/drip)",
    r"\bim\b": "into the muscle (injection)",
    r"\bsl\b": "dissolved under the tongue",
    r"\bneb\b": "via nebulizer (breathing mist)",
    r"\bsos\b": "in an emergency / when required",
    r"\btab\b": "tablet",
    r"\bcap\b": "capsule",
    r"\bsyp\b": "syrup / liquid",
    r"\binj\b": "injection",
    r"\bmg\b": "milligrams",
    r"\bgm\b": "grams",
    r"\bml\b": "milliliters",
    r"\bgtts\b": "drops"
}

# Local language abbreviation translations
RX_LOCAL_TRANSLATIONS = {
    "hi": {
        "by mouth (swallow with water)": "मुंह से (पानी के साथ निगलें)",
        "twice a day (every 12 hours)": "दिन में दो बार (सुबह और शाम)",
        "3 times a day (morning, afternoon, night)": "दिन में 3 बार (सुबह, दोपहर, रात)",
        "4 times a day (every 6 hours)": "दिन में 4 बार (हर 6 घंटे में)",
        "once a day": "दिन में एक बार",
        "at bedtime": "सोने से पहले",
        "only as needed when symptoms appear": "केवल आवश्यकता पड़ने पर",
        "before meals (on an empty stomach)": "भोजन से पहले (खाली पेट)",
        "after meals (with or after food)": "भोजन के बाद (खाने के साथ या बाद)",
        "immediately / right now": "तुरंत / अभी",
        "tablet": "गोली (टैबलेट)",
        "capsule": "कैप्सूल",
        "syrup / liquid": "सिरप (तरल दवा)",
        "injection": "सुई (इंजेक्शन)",
        "in an emergency / when required": "आपात स्थिति में / ज़रूरत होने पर"
    },
    "bn": {
        "by mouth (swallow with water)": "মুখে (জল দিয়ে গিলুন)",
        "twice a day (every 12 hours)": "দিনে দুবার (সকালে এবং রাতে)",
        "3 times a day (morning, afternoon, night)": "দিনে ৩ বার (সকাল, দুপুর, রাত)",
        "4 times a day (every 6 hours)": "দিনে ৪ বার (প্রতি ৬ ঘণ্টায়)",
        "once a day": "দিনে একবার",
        "at bedtime": "শোবার আগে",
        "only as needed when symptoms appear": "শুধুমাত্র লক্ষণ দেখা দিলে / প্রয়োজন হলে",
        "before meals (on an empty stomach)": "খাওয়ার আগে (খালি পেটে)",
        "after meals (with or after food)": "খাওয়ার পরে (খাবারের সাথে বা পরে)",
        "immediately / right now": "অবিলম্বে / এখনই",
        "tablet": "ট্যাবলেট",
        "capsule": "ক্যাপসুল",
        "syrup / liquid": "সিরাপ (তরল ওষুধ)",
        "injection": "ইনজেকশন",
        "in an emergency / when required": "জরুরী প্রয়োজনে"
    },
    "es": {
        "by mouth (swallow with water)": "por vía oral (tragar con agua)",
        "twice a day (every 12 hours)": "dos veces al día (cada 12 horas)",
        "3 times a day (morning, afternoon, night)": "3 veces al día (mañana, tarde, noche)",
        "4 times a day (every 6 hours)": "4 veces al día (cada 6 horas)",
        "once a day": "una vez al día",
        "at bedtime": "antes de acostarse",
        "only as needed when symptoms appear": "solo según sea necesario",
        "before meals (on an empty stomach)": "antes de las comidas (en ayunas)",
        "after meals (with or after food)": "después de las comidas",
        "immediately / right now": "de inmediato / ya mismo",
        "tablet": "tableta / comprimido",
        "capsule": "cápsula",
        "syrup / liquid": "jarabe",
        "injection": "inyección",
        "in an emergency / when required": "en caso de emergencia / según necesidad"
    },
    "fr": {
        "by mouth (swallow with water)": "par voie orale (avaler avec de l'eau)",
        "twice a day (every 12 hours)": "deux fois par jour (matin et soir)",
        "3 times a day (morning, afternoon, night)": "3 fois par jour (matin, midi, soir)",
        "4 times a day (every 6 hours)": "4 fois par jour (toutes les 6 heures)",
        "once a day": "une fois par jour",
        "at bedtime": "au coucher",
        "only as needed when symptoms appear": "seulement en cas de besoin",
        "before meals (on an empty stomach)": "avant les repas (à jeun)",
        "after meals (with or after food)": "après les repas",
        "immediately / right now": "immédiatement / tout de suite",
        "tablet": "comprimé",
        "capsule": "gélule",
        "syrup / liquid": "sirop",
        "injection": "injection",
        "in an emergency / when required": "en cas d'urgence / au besoin"
    }
}

# Clinical Jargon translation dictionary with multilingual meanings
MEDICAL_JARGON = {
    "dyspnea": {
        "en": "difficulty breathing or shortness of breath",
        "hi": "सांस लेने में कठिनाई या सांस फूलना",
        "bn": "শ্বাসকষ্ট বা দম বন্ধ ভাব",
        "es": "dificultad para respirar o falta de aire",
        "fr": "difficulté à respirer ou essoufflement"
    },
    "tachypnea": {
        "en": "rapid, shallow breathing",
        "hi": "तेज़ और उथली सांस लेना",
        "bn": "দ্রুত অগভীর শ্বাস নেওয়া",
        "es": "respiración rápida y superficial",
        "fr": "respiration rapide et superficielle"
    },
    "hypertension": {
        "en": "high blood pressure",
        "hi": "उच्च रक्तचाप (हाई बीपी)",
        "bn": "উচ্চ রক্তচাপ (হাই ব্লাড প্রেশার)",
        "es": "presión arterial alta",
        "fr": "hypertension artérielle"
    },
    "hypotension": {
        "en": "dangerously low blood pressure",
        "hi": "खतरनाक रूप से कम रक्तचाप (लो बीपी)",
        "bn": "বিপজ্জনকভাবে কম রক্তচাপ",
        "es": "presión arterial peligrosamente baja",
        "fr": "tension artérielle anormalement basse"
    },
    "tachycardia": {
        "en": "abnormally fast heart rate (racing heart)",
        "hi": "दिल की धड़कन का बहुत तेज़ होना",
        "bn": "হৃদস্পন্দন অস্বাভাবিক দ্রুত হওয়া",
        "es": "frecuencia cardíaca acelerada",
        "fr": "fréquence cardiaque anormalement rapide"
    },
    "bradycardia": {
        "en": "abnormally slow heart rate",
        "hi": "दिल की धड़कन का बहुत धीमा होना",
        "bn": "হৃদস্পন্দন অস্বাভাবিক ধীর হওয়া",
        "es": "frecuencia cardíaca anormalmente lenta",
        "fr": "fréquence cardiaque anormalement lente"
    },
    "arrhythmia": {
        "en": "irregular heartbeat pattern",
        "hi": "दिल की धड़कन का अनियमित होना",
        "bn": "অনিয়মিত হৃদস্পন্দন",
        "es": "latido cardíaco irregular",
        "fr": "rythme cardiaque irrégulier"
    },
    "myocardial infarction": {
        "en": "heart attack (blockage of blood flow to heart)",
        "hi": "दिल का दौरा (हार्ट अटैक)",
        "bn": "হার্ট অ্যাটাক (হৃদরোগের আক্রমণ)",
        "es": "ataque cardíaco / infarto de miocardio",
        "fr": "infarctus du myocarde (crise cardiaque)"
    },
    "angina": {
        "en": "chest pain from reduced blood flow to the heart",
        "hi": "कम रक्त प्रवाह के कारण सीने में दर्द (एंजाइना)",
        "bn": "বুকে চাপযুক্ত তীব্র ব্যথা",
        "es": "dolor en el pecho por falta de riego sanguíneo",
        "fr": "douleur thoracique par manque d'oxygénation"
    },
    "cerebrovascular accident": {
        "en": "stroke (brain circulation emergency)",
        "hi": "ब्रेन स्ट्रोक (मस्तिष्क में रक्त प्रवाह रुकना)",
        "bn": "মস্তিষ্কে রক্তক্ষরণ বা স্ট্রোক",
        "es": "accidente cerebrovascular (derrame cerebral)",
        "fr": "accident vasculaire cérébral (AVC)"
    },
    "cva": {
        "en": "stroke (brain circulation emergency)",
        "hi": "ब्रेन स्ट्रोक",
        "bn": "মস্তিষ্কের স্ট্রোক",
        "es": "derrame cerebral",
        "fr": "accident vasculaire cérébral"
    },
    "syncope": {
        "en": "fainting or sudden temporary blackout",
        "hi": "बेहोशी या अचानक चक्कर खाकर गिरना",
        "bn": "হঠাৎ জ্ঞান হারানো বা মূর্ছা যাওয়া",
        "es": "desmayo o pérdida temporal del conocimiento",
        "fr": "syncope ou évanouissement temporaire"
    },
    "edema": {
        "en": "swelling caused by excess fluid trapped in tissues",
        "hi": "शरीर के अंगों में पानी भरने से सूजन",
        "bn": "শরীরে অতিরিক্ত তরল জমে ফোলা ভাব",
        "es": "hinchazón por retención de líquidos",
        "fr": "gonflement causé par accumulation de liquide"
    },
    "cyanosis": {
        "en": "bluish skin tint indicating low oxygen in blood",
        "hi": "खून में ऑक्सीजन की कमी से त्वचा का नीला पड़ना",
        "bn": "রক্তে অক্সিজেনের ঘাটতিতে ত্বক নীলচে হওয়া",
        "es": "coloración azulada por falta de oxígeno",
        "fr": "teinte bleuâtre due au manque d'oxygène"
    },
    "hypoxia": {
        "en": "dangerously low oxygen levels in tissues",
        "hi": "शरीर के ऊतकों में खतरनाक रूप से कम ऑक्सीजन",
        "bn": "শরীরে অক্সিজেনের মারাত্মক ঘাটতি",
        "es": "nivel de oxígeno peligrosamente bajo",
        "fr": "manque sévère d'oxygène dans les tissus"
    },
    "febrile": {
        "en": "having a fever / high body temperature",
        "hi": "बुखार होना (तेज़ तापमान)",
        "bn": "জ্বর হওয়া (উচ্চ তাপমাত্রা)",
        "es": "con fiebre / temperatura alta",
        "fr": "fiévreux / température élevée"
    },
    "afebrile": {
        "en": "normal body temperature (no fever)",
        "hi": "सामान्य तापमान (बुखार नहीं है)",
        "bn": "স্বাভাবিক তাপমাত্রা (জ্বর নেই)",
        "es": "sin fiebre (temperatura normal)",
        "fr": "sans fièvre"
    },
    "contusion": {
        "en": "deep bruise",
        "hi": "भीतरी गंभीर चोट या गुमचोट",
        "bn": "অভ্যন্তরীণ গভীর আঘাত বা ক্ষত",
        "es": "moretón o hematoma profundo",
        "fr": "contusion ou ecchymose profonde"
    },
    "laceration": {
        "en": "deep skin cut or open wound",
        "hi": "गहरा घाव या खुला चीरा",
        "bn": "গভীর ক্ষত বা চামড়া কেটে যাওয়া",
        "es": "corte profundo o herida abierta",
        "fr": "coupure profonde ou plaie ouverte"
    },
    "hypoglycemia": {
        "en": "dangerously low blood sugar level",
        "hi": "रक्त में शुगर की खतरनाक कमी",
        "bn": "রক্তে সুগারের মাত্রা বিপজ্জনকভাবে কমে যাওয়া",
        "es": "nivel de azúcar en sangre peligrosamente bajo",
        "fr": "chute dangereuse de la glycémie"
    },
    "hyperglycemia": {
        "en": "abnormally high blood sugar level",
        "hi": "रक्त में बहुत अधिक शुगर (हाई ब्लड शुगर)",
        "bn": "রক্তে শর্করার মাত্রা অতিরিক্ত বৃদ্ধি পাওয়া",
        "es": "nivel de azúcar en sangre anormalmente alto",
        "fr": "taux de sucre dans le sang anormalement élevé"
    },
    "wheezing": {
        "en": "whistling breath sound from narrowed breathing tubes",
        "hi": "सांस लेते समय सीटी जैसी आवाज़ आना",
        "bn": "শ্বাস নেওয়ার সময় বাঁশির মতো শব্দ",
        "es": "silbido al respirar por vías respiratorias estrechas",
        "fr": "sifflement respiratoire"
    },
    "sepsis": {
        "en": "extreme, life-threatening response to an infection",
        "hi": "गंभीर संक्रमण की जानलेवा स्थिति (सेप्सिस)",
        "bn": "মারাত্মক সংক্রমণের জীবনঘাতী প্রতিক্রিয়া",
        "es": "respuesta potencialmente mortal a una infección",
        "fr": "infection généralisée grave"
    },
    "npo": {
        "en": "nothing by mouth (do NOT eat or drink anything)",
        "hi": "मुंह से कुछ न लें (खाना-पीना बिल्कुल मना है)",
        "bn": "মুখে কিছু খাওয়া বা পান করা সম্পূর্ণ নিষেধ",
        "es": "nada por boca (no comer ni beber nada)",
        "fr": "ne rien avaler (ni manger ni boire)"
    },
    "ambulatory": {
        "en": "able to walk independently",
        "hi": "स्वयं चलने में सक्षम",
        "bn": "নিজে নিজে হাঁটতে সক্ষম",
        "es": "capaz de caminar de forma independiente",
        "fr": "capable de marcher seul"
    }
}

# Common emergency and general medicines database with multilingual descriptions
COMMON_DRUGS = {
    "augmentin": {
        "generic": "Amoxicillin + Clavulanic Acid",
        "category": "Broad-Spectrum Antibiotic",
        "purpose": {
            "en": "Kills bacterial infections in chest, throat, skin, or urinary tract.",
            "hi": "छाती, गले, त्वचा या यूरिनरी ट्रैक्ट के बैक्टीरियल संक्रमण को खत्म करता है।",
            "bn": "বুক, গলা, ত্বক বা মূত্রনালীর ব্যাকটেরিয়া সংক্রমণ নিরাময় করে।",
            "es": "Elimina infecciones bacterianas en pecho, garganta, piel o tracto urinario.",
            "fr": "Élimine les infections bactériennes de la poitrine, de la gorge et de la peau."
        },
        "instructions": {
            "en": "Take at the start of a meal with water. Complete full course.",
            "hi": "भोजन के आरंभ में पानी के साथ लें। पूरा कोर्स समाप्त करें।",
            "bn": "খাবার শুরুতে জল দিয়ে খান। সম্পূর্ণ কোর্স শেষ করুন।",
            "es": "Tomar al inicio de una comida con agua. Completar todo el tratamiento.",
            "fr": "À prendre au début du repas avec un verre d'eau."
        },
        "warning": {
            "en": "Do NOT take if allergic to Penicillin. Report rash or facial swelling immediately.",
            "hi": "पेनिसिलिन से एलर्जी होने पर बिल्कुल न लें। सूजन या चकत्ते होने पर तुरंत डॉक्टर को बताएं।",
            "bn": "পেনিসিলিন এলার্জি থাকলে কখনই খাবেন না। ফুসকুড়ি বা ফোলা দেখলে অবিলম্বে ডাক্তার দেখান।",
            "es": "NO tomar si es alérgico a la penicilina. Reportar hinchazón facial de inmediato.",
            "fr": "Ne PAS prendre en cas d'allergie à la pénicilline."
        }
    },
    "amoxicillin": {
        "generic": "Amoxicillin",
        "category": "Penicillin Antibiotic",
        "purpose": {
            "en": "Treats bacterial infections.",
            "hi": "बैक्टीरियल संक्रमण का इलाज करता है।",
            "bn": "ব্যাকটেরিয়াল সংক্রমণের চিকিৎসা করে।",
            "es": "Trata infecciones bacterianas.",
            "fr": "Traite les infections bactériennes."
        },
        "instructions": {
            "en": "Take with water. Space doses evenly throughout the day.",
            "hi": "पानी के साथ लें। खुराकों के बीच समान समय अंतराल रखें।",
            "bn": "জল দিয়ে খান। ডোজগুলি দিনের সমান ব্যবধানে নিন।",
            "es": "Tomar con agua a intervalos regulares durante el día.",
            "fr": "Prendre avec de l'eau à intervalles réguliers."
        },
        "warning": {
            "en": "Contraindicated in penicillin-allergic patients.",
            "hi": "पेनिसिलिन से एलर्जी वाले मरीजों के लिए वर्जित है।",
            "bn": "পেনিসিলিন অ্যালার্জিযুক্ত রোগীদের জন্য সম্পূর্ণ নিষিদ্ধ।",
            "es": "Contraindicado en pacientes con alergia a la penicilina.",
            "fr": "Contre-indiqué en cas d'allergie à la pénicilline."
        }
    },
    "paracetamol": {
        "generic": "Acetaminophen / Paracetamol",
        "category": "Antipyretic & Analgesic",
        "purpose": {
            "en": "Lowers fever and relieves mild to moderate pain or headaches.",
            "hi": "बुखार कम करता है और सिरदर्द या बदन दर्द से राहत देता है।",
            "bn": "জ্বর কমায় এবং মাঝারি ব্যথা বা মাথাব্যথা দূর করে।",
            "es": "Reduce la fiebre y alivia el dolor leve a moderado.",
            "fr": "Fait baisser la fièvre et soulage les douleurs légères à modérées."
        },
        "instructions": {
            "en": "Take 1 tablet every 4 to 6 hours as needed. Do not exceed 4000mg in 24 hours.",
            "hi": "आवश्यकतानुसार हर 4 से 6 घंटे में 1 गोली लें। 24 घंटे में 4000mg से अधिक न लें।",
            "bn": "প্রয়োজনে প্রতি ৪ থেকে ৬ ঘণ্টায় ১টি করে ট্যাবলেট নিন। ২৪ ঘণ্টায় ৪০০০ মিলিগ্রামের বেশি নয়।",
            "es": "Tomar 1 comprimido cada 4 a 6 horas. No exceder de 4000 mg en 24 horas.",
            "fr": "Prendre 1 comprimé toutes les 4 à 6 heures. Maximum 4000 mg par 24 heures."
        },
        "warning": {
            "en": "Excess doses can cause serious liver injury.",
            "hi": "अधिक खुराक से लीवर को गंभीर नुकसान हो सकता है।",
            "bn": "অতিরিক্ত মাত্রায় খেলে লিভারের গুরুতর ক্ষতি হতে পারে।",
            "es": "El exceso de dosis puede causar daño hepático grave.",
            "fr": "Le surdosage peut provoquer de graves lésions hépatiques."
        }
    },
    "dolo": {
        "generic": "Paracetamol 650mg",
        "category": "Antipyretic & Analgesic",
        "purpose": {
            "en": "Relieves high fever and body ache.",
            "hi": "तेज़ बुखार और बदन दर्द में राहत देता है।",
            "bn": "উচ্চ জ্বর এবং শারীরিক ব্যথা কমায়।",
            "es": "Alivia la fiebre alta y el dolor corporal.",
            "fr": "Soulage la fièvre élevée et les courbatures."
        },
        "instructions": {
            "en": "Take after meals with water. Maximum 3 to 4 times a day.",
            "hi": "खाने के बाद पानी के साथ लें। दिन में अधिकतम 3 से 4 बार।",
            "bn": "খাওয়ার পরে জল দিয়ে সেবন করুন। দিনে সর্বোচ্চ ৩ থেকে ৪ বার।",
            "es": "Tomar después de comer con agua. Máximo 3 o 4 veces al día.",
            "fr": "Prendre après les repas avec de l'eau. Maximum 3 à 4 fois par jour."
        },
        "warning": {
            "en": "Keep at least 4-6 hours gap between doses.",
            "hi": "खुराकों के बीच कम से कम 4 से 6 घंटे का अंतर रखें।",
            "bn": "প্রতিটি ডোজের মধ্যে কমপক্ষে ৪-৬ ঘণ্টার ব্যবধান রাখুন।",
            "es": "Mantener al menos 4-6 horas entre cada dosis.",
            "fr": "Respecter un intervalle d'au moins 4 à 6 heures entre chaque prise."
        }
    },
    "metformin": {
        "generic": "Metformin",
        "category": "Antidiabetic (Biguanide)",
        "purpose": {
            "en": "Lowers blood glucose levels by helping the body use insulin better.",
            "hi": "शरीर में इंसुलिन के सही उपयोग से ब्लड शुगर को नियंत्रित करता है।",
            "bn": "রক্তের শর্করার মাত্রা নিয়ন্ত্রণ করে ডায়াবেটিস নিয়ন্ত্রণে রাখে।",
            "es": "Reduce los niveles de glucosa en sangre mejorando el uso de la insulina.",
            "fr": "Régule la glycémie dans le sang pour le diabète."
        },
        "instructions": {
            "en": "Take strictly with or right after meals to minimize stomach upset.",
            "hi": "पेट की परेशानी से बचने के लिए भोजन के साथ या तुरंत बाद लें।",
            "bn": "পেটের সমস্যা এড়াতে খাবারের সাথে বা খাওয়ার পরেই খান।",
            "es": "Tomar estrictamente con o inmediatamente después de las comidas.",
            "fr": "Prendre pendant ou immédiatement après les repas."
        },
        "warning": {
            "en": "Report unusual muscle pain or trouble breathing immediately.",
            "hi": "मांसपेशियों में असामान्य दर्द या सांस की समस्या होने पर तुरंत बताएं।",
            "bn": "অস্বাভাবিক পেশী ব্যথা বা শ্বাসকষ্ট হলে অবিলম্বে ডাক্তারকে জানান।",
            "es": "Informar inmediatamente sobre dolor muscular inusual o falta de aire.",
            "fr": "Signaler immédiatement toute douleur musculaire inhabituelle."
        }
    },
    "amlodipine": {
        "generic": "Amlodipine Besylate",
        "category": "Calcium Channel Blocker (Blood Pressure)",
        "purpose": {
            "en": "Relaxes blood vessels to lower high blood pressure and prevent chest pain.",
            "hi": "रक्त वाहिकाओं को शिथिल कर हाई बीपी कम करता है।",
            "bn": "রক্তনালী প্রসারিত করে উচ্চ রক্তচাপ নিয়ন্ত্রণ করে।",
            "es": "Relaja los vasos sanguíneos para reducir la presión arterial alta.",
            "fr": "Relaxe les vaisseaux sanguins pour abaisser la tension artérielle."
        },
        "instructions": {
            "en": "Take once daily at the same time, with or without food.",
            "hi": "प्रतिदिन एक निश्चित समय पर लें, भोजन के साथ या बिना भोजन के।",
            "bn": "প্রতিদিন একই সময়ে খান, খাবারের সাথে বা আগে।",
            "es": "Tomar una vez al día a la misma hora.",
            "fr": "Prendre une fois par jour à heure fixe."
        },
        "warning": {
            "en": "May cause mild ankle swelling or dizziness when standing up quickly.",
            "hi": "टखनों में हल्की सूजन या अचानक खड़े होने पर चक्कर आ सकते हैं।",
            "bn": "গোড়ালিতে হালকা ফোলা বা দ্রুত দাঁড়ালে মাথা ঘোরা হতে পারে।",
            "es": "Puede causar leve hinchazón en tobillos o mareos al levantarse.",
            "fr": "Peut provoquer un léger gonflement des chevilles ou des vertiges."
        }
    },
    "salbutamol": {
        "generic": "Albuterol / Salbutamol",
        "category": "Bronchodilator (Inhaler / Nebulizer)",
        "purpose": {
            "en": "Opens up constricted airways during asthma attacks or breathing distress.",
            "hi": "अस्थमा के दौरे या सांस फूलने पर श्वासनलियों को तुरंत खोलता है।",
            "bn": "হাঁপানি বা শ্বাসকষ্টের সময় শ্বাসনালী উন্মুক্ত করে দ্রুত স্বস্তি দেয়।",
            "es": "Abre las vías respiratorias en ataques de asma o dificultad para respirar.",
            "fr": "Ouvre les voies respiratoires lors des crises d'asthme."
        },
        "instructions": {
            "en": "Inhale 1-2 puffs as needed when breathless. Shake canister well.",
            "hi": "सांस फूलने पर आवश्यकतानुसार 1-2 पफ इनहेल करें। कैनिस्टर को अच्छी तरह हिलाएं।",
            "bn": "শ্বাসকষ্ট হলে প্রয়োজনমতো ১-২টি পাফ নিন। ব্যবহারের আগে ক্যানিস্টার ঝাঁকিয়ে নিন।",
            "es": "Inhalar 1-2 pulverizaciones según necesidad. Agitar bien el inhalador.",
            "fr": "Inhaler 1 à 2 bouffées au besoin. Bien agiter avant emploi."
        },
        "warning": {
            "en": "May cause rapid heartbeat or shaky hands temporarily. If severe, seek ER.",
            "hi": "अस्थायी रूप से दिल की धड़कन बढ़ सकती है या हाथ कांप सकते हैं। अधिक परेशानी हो तो तुरंत ER जाएं।",
            "bn": "সাময়িক দ্রুত হৃদস্পন্দন বা হাত কাঁপুনি হতে পারে। তীব্র হলে অবিলম্বে হাসপাতালে যান।",
            "es": "Puede causar palpitaciones o temblores pasajeros. Si empeora, acuda a urgencias.",
            "fr": "Peut provoquer des palpitations passagères. En cas d'aggravation, consulter d'urgence."
        }
    },
    "aspirin": {
        "generic": "Acetylsalicylic Acid (Disprin / Ecosprin)",
        "category": "Blood Thinner & Antiplatelet",
        "purpose": {
            "en": "Prevents blood clots in heart attacks, angina, or stroke emergencies.",
            "hi": "हार्ट अटैक या स्ट्रोक की आपात स्थिति में रक्त के थक्के जमने से रोकता है।",
            "bn": "হার্ট অ্যাটাক বা স্ট্রোকের জরুরি পরিস্থিতিতে রক্ত জমাট বাঁধতে বাধা দেয়।",
            "es": "Previene coágulos sanguíneos en emergencias de infarto o accidente cerebrovascular.",
            "fr": "Prévient la formation de caillots sanguins lors d'un infarctus ou AVC."
        },
        "instructions": {
            "en": "In suspected heart attack: chew and swallow 300mg/325mg tablet immediately while waiting for ambulance.",
            "hi": "हार्ट अटैक का संदेह होने पर: एम्बुलेंस की प्रतीक्षा करते हुए तुरंत 300mg/325mg गोली चबाकर निगल लें।",
            "bn": "হার্ট অ্যাটাক সন্দেহ হলে: অ্যাম্বুলেন্স আসার অপেক্ষা করার সময়ই একটি ৩০০/৩২৫ মিলিগ্রাম ট্যাবলেট চিবিয়ে গিলে ফেলুন।",
            "es": "En sospecha de ataque cardíaco: masticar y tragar 300 mg de inmediato mientras espera la ambulancia.",
            "fr": "En cas de suspicion d'infarctus: mâcher et avaler 300 mg immédiatement en attendant les secours."
        },
        "warning": {
            "en": "Avoid if active stomach ulcer or bleeding disorder.",
            "hi": "पेट के अल्सर या रक्तस्राव विकार होने पर न लें।",
            "bn": "পেটের আলসার বা রক্তক্ষরণজনিত সমস্যা থাকলে এড়িয়ে চলুন।",
            "es": "Evitar si tiene úlcera gástrica activa o trastornos hemorrágicos.",
            "fr": "Éviter en cas d'ulcère gastrique actif ou de troubles de la coagulation."
        }
    }
}

# Local language labels and prompts
LOCAL_HEADERS = {
    "en": {
        "title": "Medical Explanation in Plain Language",
        "greeting": "Hello. Here is your medical explanation in simple words.",
        "med_intro": "Medication details:",
        "jargon_intro": "Clinical conditions explained:",
        "warnings_intro": "Critical Safety Warnings:",
        "allergy_alert": "CRITICAL ALLERGY CHECK: Verify that the patient has no Penicillin allergies before taking.",
        "dyspnea_alert": "RESPIRATORY DISTRESS WARNING: Low oxygen or breathing difficulty detected. Keep patient upright and prepare emergency oxygen/nebulizer.",
        "cardiac_alert": "CARDIAC EMERGENCY: Call for ALS Ambulance immediately. Keep patient calm and seated.",
        "npo_alert": "FASTING INSTRUCTION (NPO): Patient must NOT be given any water, food, or oral medication until cleared by a doctor."
    },
    "hi": {
        "title": "सरल हिंदी में दवा पर्चे का विवरण",
        "greeting": "नमस्ते। यहाँ आपके पर्चे का सरल एवं स्पष्ट विवरण दिया गया है।",
        "med_intro": "दवाइयों के निर्देश:",
        "jargon_intro": "चिकित्सीय स्थितियों का अर्थ:",
        "warnings_intro": "महत्वपूर्ण सुरक्षा चेतावनियाँ:",
        "allergy_alert": "गंभीर एलर्जी चेतावनी: दवा लेने से पहले सुनिश्चित करें कि मरीज को पेनिसिलिन से एलर्जी तो नहीं है।",
        "dyspnea_alert": "सांस की गंभीर चेतावनी: ऑक्सीजन की कमी या सांस में तकलीफ पाई गई है। मरीज को सीधा बैठाएं और आपातकालीन ऑक्सीजन तैयार रखें।",
        "cardiac_alert": "हृदय आपातकाल: तुरंत ALS एम्बुलेंस बुलाएं। मरीज को शांत और बैठाए रखें।",
        "npo_alert": "उपवास निर्देश (NPO): डॉक्टर की अनुमति के बिना मरीज को पानी, भोजन या कोई मौखिक दवा बिल्कुल न दें।"
    },
    "bn": {
        "title": "সহজ বাংলায় প্রেসক্রিপশনের বিবরণ",
        "greeting": "নমস্কার। এখানে আপনার ওষুধের প্রেসক্রিপশনের সহজ ব্যাখ্যা দেওয়া হলো।",
        "med_intro": "ওষুধ সেবনের নিয়মাবলী:",
        "jargon_intro": "চিকিৎসা পরিভাষার সহজ অর্থ:",
        "warnings_intro": "জরুরী নিরাপত্তা সতর্কতা:",
        "allergy_alert": "গুরুতর অ্যালার্জি সতর্কতা: ওষুধ সেবনের আগে নিশ্চিত করুন যে রোগীর পেনিসিলিন অ্যালার্জি নেই।",
        "dyspnea_alert": "শ্বাসকষ্ট সতর্কতা: কম অক্সিজেন বা শ্বাসকষ্ট চিহ্নিত হয়েছে। রোগীকে সোজা বসিয়ে রাখুন এবং জরুরী অক্সিজেনের ব্যবস্থা করুন।",
        "cardiac_alert": "হৃদরোগের জরুরী অবস্থা: অবিলম্বে উন্নত অ্যাম্বুলেন্স ডাকুন। রোগীকে শান্ত ও স্থির রাখুন।",
        "npo_alert": "খাবারের নিষেধাজ্ঞা (NPO): চিকিৎসকের অনুমতি ছাড়া রোগীকে কোনও জল, খাবার বা মুখে খাওয়ার ওষুধ দেবেন না।"
    },
    "es": {
        "title": "Explicación médica en lenguaje sencillo",
        "greeting": "Hola. Aquí tiene la explicación de su prescripción médica en palabras sencillas.",
        "med_intro": "Detalles de medicamentos:",
        "jargon_intro": "Términos médicos explicados:",
        "warnings_intro": "Advertencias críticas de seguridad:",
        "allergy_alert": "ALERTA CRÍTICA DE ALERGIA: Verifique que el paciente no tenga alergia a la penicilina.",
        "dyspnea_alert": "ALERTA RESPIRATORIA: Dificultad respiratoria detectada. Mantenga al paciente erguido y prepare oxígeno.",
        "cardiac_alert": "EMERGENCIA CARDÍACA: Solicite una ambulancia de soporte vital de inmediato.",
        "npo_alert": "AYUNO ESTRICTO (NPO): El paciente NO debe recibir agua, comida ni medicación oral hasta nueva orden."
    },
    "fr": {
        "title": "Explication médicale en langage clair",
        "greeting": "Bonjour. Voici l'explication simple de votre ordonnance médicale.",
        "med_intro": "Détails des médicaments:",
        "jargon_intro": "Termes médicaux expliqués:",
        "warnings_intro": "Avertissements de sécurité importants:",
        "allergy_alert": "ALERTE ALLERGIE CRITIQUE: Vérifier l'absence d'allergie à la pénicilline.",
        "dyspnea_alert": "ALERTE DÉTRESSE RESPIRATOIRE: Difficulté respiratoire détectée. Garder le patient assis et préparer l'oxygène.",
        "cardiac_alert": "URGENCE CARDIAQUE: Appeler immédiatement une ambulance de réanimation.",
        "npo_alert": "JEÛNE STRICT (NPO): Le patient ne doit rien boire, ni manger, ni prendre par voie orale."
    }
}

def simplify_medical_text(raw_text: str, target_language: str = "en") -> dict:
    """
    Parses medical notes or prescriptions and returns a comprehensive,
    user-friendly breakdown with localized explanations, schedule, warnings, and audio script.
    """
    lang = (target_language or "en").lower()
    if lang not in LOCAL_HEADERS:
        lang = "en"

    headers = LOCAL_HEADERS[lang]

    if not raw_text or not raw_text.strip():
        return {
            "summary": "No text provided to analyze.",
            "language": lang,
            "layman_translation": "",
            "medications": [],
            "jargon_detected": [],
            "safety_alerts": [],
            "speech_text": "Please provide a medical note or prescription to translate."
        }

    text_lower = raw_text.lower()
    
    # 1. Identify Jargon terms with localized meanings
    detected_jargon = []
    for term, meanings in MEDICAL_JARGON.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, text_lower):
            plain_meaning = meanings.get(lang) or meanings.get("en", "")
            detected_jargon.append({
                "term": term.title(),
                "plain_meaning": plain_meaning
            })

    # 2. Identify Medications mentioned with localized purpose/instructions
    detected_drugs = []
    for drug_key, details in COMMON_DRUGS.items():
        if drug_key in text_lower:
            purpose_text = details["purpose"].get(lang) or details["purpose"].get("en", "")
            instruct_text = details["instructions"].get(lang) or details["instructions"].get("en", "")
            warning_text = details["warning"].get(lang) or details["warning"].get("en", "")
            
            detected_drugs.append({
                "name": drug_key.title(),
                "generic": details["generic"],
                "category": details["category"],
                "purpose": purpose_text,
                "how_to_take": instruct_text,
                "warning": warning_text
            })

    # 3. Translate Latin abbreviations into human schedule in English, then localize
    translated_schedule = raw_text
    for abbrev, meaning in RX_ABBREVIATIONS.items():
        translated_schedule = re.sub(abbrev, f"({meaning})", translated_schedule, flags=re.IGNORECASE)

    # If non-English, replace common phrases with localized ones
    if lang in RX_LOCAL_TRANSLATIONS:
        loc_map = RX_LOCAL_TRANSLATIONS[lang]
        for en_phrase, loc_phrase in loc_map.items():
            translated_schedule = translated_schedule.replace(f"({en_phrase})", f"({loc_phrase})")

    # 4. Generate Safety Alerts in target language
    safety_alerts = []
    if "penicillin" in text_lower or "augmentin" in text_lower or "amoxicillin" in text_lower:
        safety_alerts.append(headers["allergy_alert"])
    if "dyspnea" in text_lower or "cyanosis" in text_lower or "hypoxia" in text_lower:
        safety_alerts.append(headers["dyspnea_alert"])
    if "chest pain" in text_lower or "angina" in text_lower or "myocardial infarction" in text_lower:
        safety_alerts.append(headers["cardiac_alert"])
    if "npo" in text_lower:
        safety_alerts.append(headers["npo_alert"])

    # 5. Build high-clarity Plain Language Summary
    summary_parts = []
    if lang == "en":
        if detected_drugs:
            summary_parts.append(f"This prescription contains {len(detected_drugs)} medication(s): {', '.join([d['name'] for d in detected_drugs])}.")
        if detected_jargon:
            summary_parts.append(f"Identified {len(detected_jargon)} clinical condition term(s): {', '.join([j['term'] for j in detected_jargon])}.")
        if not summary_parts:
            summary_parts.append("Translated medical abbreviations and clinical terminology into simple patient guidelines.")
    elif lang == "hi":
        if detected_drugs:
            summary_parts.append(f"इस पर्चे में {len(detected_drugs)} दवाइयां पहचानी गई हैं: {', '.join([d['name'] for d in detected_drugs])}।")
        if detected_jargon:
            summary_parts.append(f"कुल {len(detected_jargon)} चिकित्सकीय स्थितियां स्पष्ट की गई हैं।")
        if not summary_parts:
            summary_parts.append("दवा पर्चे की लैटिन शब्दावली को सरल हिंदी निर्देशों में परिवर्तित किया गया है।")
    elif lang == "bn":
        if detected_drugs:
            summary_parts.append(f"এই প্রেসক্রিপশনে {len(detected_drugs)}টি ওষুধ চিহ্নিত হয়েছে: {', '.join([d['name'] for d in detected_drugs])}।")
        if detected_jargon:
            summary_parts.append(f"{len(detected_jargon)}টি জটিল চিকিৎসা শব্দ ব্যাখ্যা করা হয়েছে।")
        if not summary_parts:
            summary_parts.append("প্রেসক্রিপশনের দুর্বোধ্য সংকেতগুলি সহজ বাংলায় রূপান্তর করা হয়েছে।")
    elif lang == "es":
        if detected_drugs:
            summary_parts.append(f"Esta receta contiene {len(detected_drugs)} medicamento(s): {', '.join([d['name'] for d in detected_drugs])}.")
        if detected_jargon:
            summary_parts.append(f"Se identificaron {len(detected_jargon)} término(s) clínico(s).")
    elif lang == "fr":
        if detected_drugs:
            summary_parts.append(f"Cette ordonnance contient {len(detected_drugs)} médicament(s): {', '.join([d['name'] for d in detected_drugs])}.")
        if detected_jargon:
            summary_parts.append(f"Identifié {len(detected_jargon)} terme(s) médical(aux).")

    # 6. Build Speech-ready narrative for audio read-aloud
    speech_lines = [headers["greeting"]]
    for d in detected_drugs:
        if lang == "hi":
            speech_lines.append(f"{d['name']}, {d['purpose']} इसे {d['how_to_take']}")
        elif lang == "bn":
            speech_lines.append(f"{d['name']}, {d['purpose']} এটি {d['how_to_take']}")
        elif lang == "es":
            speech_lines.append(f"{d['name']}: {d['purpose']} Instrucciones: {d['how_to_take']}.")
        elif lang == "fr":
            speech_lines.append(f"{d['name']}: {d['purpose']} Posologie: {d['how_to_take']}.")
        else:
            speech_lines.append(f"{d['name']} is a {d['category']} used to {d['purpose']}. Instructions: {d['how_to_take']}.")

    for j in detected_jargon:
        if lang == "hi":
            speech_lines.append(f"{j['term']} का अर्थ है {j['plain_meaning']}।")
        elif lang == "bn":
            speech_lines.append(f"{j['term']} মানে হলো {j['plain_meaning']}।")
        elif lang == "es":
            speech_lines.append(f"El término {j['term']} significa {j['plain_meaning']}.")
        elif lang == "fr":
            speech_lines.append(f"Le terme {j['term']} signifie {j['plain_meaning']}.")
        else:
            speech_lines.append(f"The term {j['term']} simply means {j['plain_meaning']}.")

    for s in safety_alerts:
        speech_lines.append(s)

    return {
        "summary": " ".join(summary_parts),
        "language": lang,
        "language_name": {"en": "English", "hi": "हिन्दी (Hindi)", "bn": "বাংলা (Bengali)", "es": "Español", "fr": "Français"}.get(lang, "English"),
        "layman_translation": translated_schedule,
        "medications": detected_drugs,
        "jargon_detected": detected_jargon,
        "safety_alerts": safety_alerts,
        "speech_text": " ".join(speech_lines)
    }

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    sample = "Pt presented with acute dyspnea and tachycardia. Rx: Tab Augmentin 625mg PO TID PC x 7d. Tab Dolo 650mg SOS."
    res_en = simplify_medical_text(sample, "en")
    print("EN Summary:", res_en["summary"])
    res_hi = simplify_medical_text(sample, "hi")
    print("HI Summary:", res_hi["summary"])
    res_bn = simplify_medical_text(sample, "bn")
    print("BN Summary:", res_bn["summary"])
