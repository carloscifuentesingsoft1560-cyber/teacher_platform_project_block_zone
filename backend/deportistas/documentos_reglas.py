"""Normalización determinista. No verifica autenticidad ni consulta datos externos."""
import re
import unicodedata

TIPOS_CO = ("RC","TI","CC","CE","PPT")
PAISES_ISO = tuple("""AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW""".split())
PATRON_NUMERO = r"^[A-Z0-9]+([-/][A-Z0-9]+)*$"
MOTIVOS_CAMBIO = ("completar_pendiente","correccion","nuevo_documento","anulacion_por_error")
CATALOGO_INICIAL = (
    ("RC","Registro civil de nacimiento — NUIP/NIP"),
    ("TI","Tarjeta de identidad"),
    ("CC","Cédula de ciudadanía"),
    ("CE","Cédula de extranjería"),
    ("PA","Pasaporte"),
    ("PPT","Permiso por Protección Temporal"),
    ("DNI","Documento nacional extranjero"),
)

def texto_canonico(valor):
    return unicodedata.normalize("NFKC",str(valor or "")).strip().upper()

def normalizar_identificacion(tipo, numero, pais):
    tipo=texto_canonico(tipo)
    numero=texto_canonico(numero)
    pais=texto_canonico(pais)
    if not tipo and not numero and not pais:
        return None,None,None
    if not tipo or not numero:
        raise ValueError("Indica tipo y número o deja la identificación pendiente.")
    numero="".join(numero.split())
    if tipo in TIPOS_CO:
        numero=numero.replace(".","").replace("-","")
        pais=pais or "CO"
        if pais!="CO":
            raise ValueError("El tipo documental seleccionado se emite en Colombia.")
    if pais not in PAISES_ISO:
        raise ValueError("Selecciona un país emisor válido.")
    if len(numero)>40 or not re.fullmatch(PATRON_NUMERO,numero):
        raise ValueError("Formato documental no admitido. Revisa letras, cifras y separadores.")
    return tipo,numero,pais

def enmascarar(numero):
    if not numero:
        return ""
    return "****"+(numero[-4:] if len(numero)>4 else "")

def presentacion(persona, restringida=False):
    if not persona.tipo_documento_id or not persona.numero_documento:
        return "Documento pendiente"
    numero=enmascarar(persona.numero_documento) if restringida else persona.numero_documento
    pais="" if restringida or persona.tipo_documento_id in TIPOS_CO else " ("+persona.pais_emisor+")"
    return persona.tipo_documento_id+pais+" "+numero
