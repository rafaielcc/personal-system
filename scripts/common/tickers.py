"""
Lista partilhada de tickers (Carteira + Vigiar) para pre-marcacao automatica
de mencoes em texto (emails, mensagens Telegram), sem depender de LLM.

Cada ticker mapeia para uma lista de padroes regex (o proprio codigo do
ticker e sempre incluido; nomes de empresa so quando ha confianca razoavel
na grafia, para evitar falsos negativos por nome errado — o codigo sozinho
ja e suficiente para a deteccao funcionar).

Usado por gmail_export.py e telegram_export.py via find_tickers(texto).
"""

import re

TICKER_PATTERNS = {
    # Carteira
    "BBAS3": [r"\bBBAS3\b", r"\bBanco do Brasil\b"],
    "BBDC3": [r"\bBBDC3\b", r"\bBradesco\b"],
    "SANB3": [r"\bSANB3\b", r"\bSantander\b"],
    "BBSE3": [r"\bBBSE3\b", r"\bBB Seguridade\b"],
    "CXSE3": [r"\bCXSE3\b", r"\bCaixa Seguridade\b"],
    "CPFE3": [r"\bCPFE3\b", r"\bCPFL\b"],
    "EGIE3": [r"\bEGIE3\b", r"\bEngie\b"],
    "TAEE11": [r"\bTAEE11\b", r"\bTaesa\b"],
    "LEVE3": [r"\bLEVE3\b", r"\bMahle\b", r"\bMetal Leve\b"],
    "ROMI3": [r"\bROMI3\b", r"\bIndustrias Romi\b"],
    "KEPL3": [r"\bKEPL3\b", r"\bKepler\s*Weber\b"],
    "SOJA3": [r"\bSOJA3\b", r"\bBoa Safra\b"],
    "CMIN3": [r"\bCMIN3\b", r"\bCSN Mine"],
    "KLBN4": [r"\bKLBN4\b", r"\bKlabin\b"],
    "RANI3": [r"\bRANI3\b", r"\bIrani\b(?!ano|anos|ana|anas)"],
    "VALE3": [r"\bVALE3\b"],
    "GRND3": [r"\bGRND3\b", r"\bGrendene\b"],
    "LREN3": [r"\bLREN3\b", r"\bLojas Renner\b", r"\bRenner\b"],
    "VULC3": [r"\bVULC3\b", r"\bVulcabras\b"],

    # Vigiar
    "ITUB3": [r"\bITUB[34]\b", r"\bIta[uú]\b"],
    "ITSA4": [r"\bITSA4\b", r"\bItausa\b"],
    "BRSR6": [r"\bBRSR6\b", r"\bBanrisul\b"],
    "BEES3": [r"\bBEES3\b", r"\bBanestes\b"],
    "PINE4": [r"\bPINE4\b", r"\bBanco Pine\b"],
    "BMGB4": [r"\bBMGB4\b", r"\bBanco BMG\b"],
    "PSSA3": [r"\bPSSA3\b", r"\bPorto Seguro\b"],
    "AURE3": [r"\bAURE3\b", r"\bAuren\b"],
    "CPLE3": [r"\bCPLE3\b", r"\bCopel\b"],
    "AXIA3": [r"\bAXIA3\b"],
    "CMIG4": [r"\bCMIG4\b", r"\bCemig\b"],
    "ENGI4": [r"\bENGI4\b", r"\bEnergisa\b"],
    "ISAE4": [r"\bISAE[34]\b", r"\bISA Energia\b"],
    "TAEE3": [r"\bTAEE3\b"],
    "ALUP11": [r"\bALUP11\b", r"\bAlupar\b"],
    "CEBR6": [r"\bCEBR6\b", r"\bCEB\b"],
    "SAPR4": [r"\bSAPR4\b", r"\bSanepar\b"],
    "CSMG3": [r"\bCSMG3\b", r"\bCopasa\b"],
    "FLRY3": [r"\bFLRY3\b", r"\bFleury\b"],
    "FRAS3": [r"\bFRAS3\b", r"\bFras-le\b"],
    "RAPT3": [r"\bRAPT3\b", r"\bRandon\b"],
    "SHUL4": [r"\bSHUL4\b", r"\bSchulz\b"],
    "MYPK3": [r"\bMYPK3\b", r"\bIochpe\b"],
    "TUPY3": [r"\bTUPY3\b", r"\bTupy\b"],
    "FESA4": [r"\bFESA4\b", r"\bFerbasa\b"],
    "POMO3": [r"\bPOMO[34]\b", r"\bMarcopolo\b"],
    "SLCE3": [r"\bSLCE3\b", r"\bSLC Agricola\b"],
    "AGRO3": [r"\bAGRO3\b", r"\bBrasilAgro\b"],
    "TTEN3": [r"\bTTEN3\b", r"\b3tentos\b"],
    "ALOS3": [r"\bALOS3\b", r"\bAllos\b"],
    "CSUD3": [r"\bCSUD3\b", r"\bCS[UÚ] Cardsystem\b"],
    "INTB3": [r"\bINTB3\b", r"\bIntelbras\b"],
    "MOVI3": [r"\bMOVI3\b", r"\bMovida\b"],
    "TIMS3": [r"\bTIMS3\b", r"\bTIM\b"],
    "VLID3": [r"\bVLID3\b", r"\bValid\b"],
    "VIVT3": [r"\bVIVT3\b", r"\bVivo\b", r"\bTelefonica Brasil\b"],
    "DEXP3": [r"\bDEXP3\b", r"\bDexco\b"],
    "ARML3": [r"\bARML3\b", r"\bArmac\b"],
    "FIQE3": [r"\bFIQE3\b", r"\bUnifique\b"],
    "HYPE3": [r"\bHYPE3\b", r"\bHypera\b"],
    "LOGG3": [r"\bLOGG3\b", r"\bLog Commercial\b"],
    "CAML3": [r"\bCAML3\b", r"\bCamil\b"],
    "CGRA3": [r"\bCGRA3\b", r"\bGrazziotin\b"],
    "JHSF3": [r"\bJHSF3\b"],
    "SYNE3": [r"\bSYNE3\b", r"\bSyn Prop\b"],
    "PETR3": [r"\bPETR[34]\b", r"\bPetrobras\b"],
    "PETR4": [r"\bPETR[34]\b", r"\bPetrobras\b"],
    "UNIP6": [r"\bUNIP6\b", r"\bUnipar\b"],
    "IRBR3": [r"\bIRBR3\b", r"\bIRB\s*\(?Re\)?\b"],
    "MRVE3": [r"\bMRVE3\b", r"\bMRV\b"],
    "SUZB3": [r"\bSUZB3\b", r"\bSuzano\b"],
    "WIZC3": [r"\bWIZC3\b", r"\bWiz\b"],

    # Fora do radar / relevantes com frequencia (nao detidos, nao vigiados)
    "WEGE3": [r"\bWEGE3\b", r"\bWEG\b"],
    "EMBR3": [r"\bEMBR3\b", r"\bEmbraer\b"],
    "PRIO3": [r"\bPRIO3\b", r"\bPRIO\b"],
    "BRAV3": [r"\bBRAV3\b", r"\bBrava Energia\b"],
    "GGBR4": [r"\bGGBR4\b", r"\bGerdau\b"],
    "NATU3": [r"\bNATU3\b", r"\bNatura\b"],
}


def find_tickers(texto: str) -> list[str]:
    """Devolve a lista ordenada de tickers cujo padrao aparece em texto."""
    if not texto:
        return []
    hits = set()
    for ticker, patterns in TICKER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, texto, re.IGNORECASE):
                hits.add(ticker)
                break
    return sorted(hits)
