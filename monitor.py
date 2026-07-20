"""
monitor.py — Monitor de Diário Oficial para convocações de concurso.

O que faz:
  1. Consulta o(s) Diário(s) Oficial(is) configurado(s) em CIDADES.
  2. Filtra publicações por palavras-chave (convocação, nomeação, posse...).
  3. Compara com o snapshot anterior (estado.json) e detecta o que é NOVO.
  4. Notifica em TODOS os canais que você tiver configurado:
        - Telegram   (se TELEGRAM_TOKEN + TELEGRAM_CHAT_ID)
        - E-mail     (se EMAIL_REMETENTE + EMAIL_SENHA_APP + EMAIL_DESTINO)
        - Push no celular via ntfy.sh (se NTFY_TOPIC)  <- ótimo pra iPhone
     Se nenhum estiver configurado, só imprime no log (bom pra testar).
  5. Salva o novo snapshot.

Feito pra rodar sozinho no GitHub Actions (grátis). Não usa IA / não gasta
token de LLM nenhum — é requests + BeautifulSoup puro.

------------------------------------------------------------------------------
ONDE VOCÊ MEXE:
  - CIDADES (logo abaixo dos adaptadores): lista das cidades que você acompanha.
  - PALAVRAS_ALVO (logo abaixo): o que dispara o aviso.
  - Os canais de notificação são configurados por SECRETS no GitHub, não aqui
    no código (ver README.md). Você não precisa colar senha nenhuma neste arquivo.
------------------------------------------------------------------------------
"""

import json
import os
import re
import smtplib
import sys
import time
import unicodedata
from datetime import datetime
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# Console do Windows às vezes é cp1252 e engasga com emoji. Força UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ARQUIVO_ESTADO = "estado.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# Palavras que indicam "chamou / vai chamar pra posse". Tudo minúsculo e SEM
# acento — a comparação ignora acento dos dois lados (ver _sem_acento).
# Adicione/remova à vontade. Ex.: inclua "reclassifica" se quiser saber de
# reclassificações também.
PALAVRAS_ALVO = [
    "convocacao",
    "convoca",
    "nomeacao",
    "nomeia",
    "posse",
    "homologacao",
    "resultado final",
    "classificacao final",
]


def _sem_acento(txt: str) -> str:
    """minúsculas + sem acento, pra comparar palavra-chave sem depender de acento."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.lower().strip()


def bate_palavra(titulo: str) -> bool:
    t = _sem_acento(titulo)
    return any(p in t for p in PALAVRAS_ALVO)


# ===========================================================================
# ADAPTADORES POR CIDADE
# ---------------------------------------------------------------------------
# Cada adaptador é uma função que devolve uma lista de dicts:
#   {"cidade", "data", "titulo", "categoria", "link"}
# Veja ADICIONAR-CIDADE.md para o passo a passo de incluir uma cidade nova.
# ===========================================================================

def adaptador_portal_padrao(nome_cidade, dominio, ano=None, termos=("concurso", "convocacao", "nomeacao")):
    """
    FÁBRICA de adaptador para prefeituras que usam a MESMA plataforma da
    Catanduvas (a URL do diário tem '/filtrarDiarioSearch' e os links são
    '/diario_view?id=N'). Para uma cidade dessas, adicionar é UMA LINHA em
    CIDADES — só trocar o domínio.

    Se a cidade usar outra plataforma, NÃO use esta fábrica: escreva um
    adaptador próprio (ver ADICIONAR-CIDADE.md).
    """
    dominio = dominio.rstrip("/")
    ano = ano or str(datetime.now().year)

    def _adaptador():
        base = f"{dominio}/filtrarDiarioSearch"
        resultados = {}  # chaveado por link, pra deduplicar
        for termo in termos:
            params = {"categoria_id": "", "ano": ano, "edicao": "", "objeto": termo, "page": 1}
            try:
                r = requests.get(base, params=params, headers=HEADERS, timeout=20)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"[{nome_cidade}] erro na busca '{termo}': {e}", file=sys.stderr)
                continue

            sopa = BeautifulSoup(r.text, "html.parser")
            tabela = sopa.find("table")
            if not tabela:
                continue

            # Página 1 basta: o diário vem ordenado do mais novo pro mais antigo,
            # então qualquer publicação NOVA sempre cai na página 1 primeiro.
            for linha in tabela.find_all("tr")[1:]:  # pula cabeçalho
                celulas = linha.find_all("td")
                if len(celulas) < 4:
                    continue
                data = celulas[0].get_text(strip=True)
                titulo = celulas[1].get_text(strip=True)
                categoria = celulas[2].get_text(strip=True)
                a = celulas[3].find("a")
                link = a["href"] if a and a.has_attr("href") else None
                if link and link.startswith("/"):
                    link = dominio + link

                if not bate_palavra(titulo):
                    continue

                chave = link or titulo
                resultados[chave] = {
                    "cidade": nome_cidade,
                    "data": data,
                    "titulo": titulo,
                    "categoria": categoria,
                    "link": link,
                }
            time.sleep(1)  # gentileza com o servidor

        return list(resultados.values())

    _adaptador.__name__ = f"adaptador_{_sem_acento(nome_cidade).replace(' ', '_')}"
    return _adaptador


def criar_adaptador_querido_diario(nome_cidade, territory_id, termos=("concurso", "convocacao", "nomeacao")):
    """
    FÁBRICA de adaptador que usa a API pública do Querido Diário
    (https://queridodiario.ok.org.br/ — projeto do Open Knowledge Brasil),
    que já indexa o Diário Oficial de milhares de municípios brasileiros.

    Isso evita ter que raspar o HTML de cada prefeitura (várias têm
    proteção anti-robô ou JS pesado). Você só precisa do "territory_id",
    que é o código IBGE de 7 dígitos do município.

    territory_id usados aqui (conferidos no IBGE):
        Goioerê-PR              4108601
        Prado Ferreira-PR       4120333
        Cambé-PR                4103701
        Marechal C. Rondon-PR   4114609

    IMPORTANTE: a cobertura do Querido Diário varia de cidade pra cidade
    (depende de quando/se o município foi indexado pelo projeto). Rode o
    monitor uma vez após configurar e confira o log: se aparecer erro de
    rede ou a cidade nunca disparar aviso nenhum por semanas, é sinal de
    que essa cidade pode não estar coberta — nesse caso, use
    adaptador_portal_padrao ou escreva um adaptador específico (ver
    ADICIONAR-CIDADE.md) apontando pro Diário Oficial da própria prefeitura.
    """
    BASE = "https://api.queridodiario.ok.org.br/gazettes"

    def _adaptador():
        resultados = {}
        for termo in termos:
            params = {
                "territory_ids": territory_id,
                "querystring": termo,
                "size": 20,
                "sort_by": "relevance",
            }
            try:
                r = requests.get(BASE, params=params, headers=HEADERS, timeout=25)
                r.raise_for_status()
                dados = r.json()
            except (requests.RequestException, ValueError) as e:
                print(f"[{nome_cidade}] erro na busca Querido Diário '{termo}': {e}", file=sys.stderr)
                continue

            for gaz in dados.get("gazettes", []):
                # o "título" aqui é o trecho (excerpt) que bateu com a busca —
                # a API não devolve um título de matéria isolado, então
                # montamos algo legível a partir do excerto + edição/data.
                excertos = gaz.get("excerpts") or []
                trecho = excertos[0].strip().replace("\n", " ") if excertos else termo
                trecho = re.sub(r"\s+", " ", trecho)[:280]

                if not bate_palavra(trecho):
                    continue

                link = gaz.get("url") or gaz.get("txt_url")
                data = gaz.get("date", "")
                chave = link or f"{nome_cidade}|{data}|{trecho[:60]}"

                resultados[chave] = {
                    "cidade": nome_cidade,
                    "data": data,
                    "titulo": f"Edição {gaz.get('edition', '?')}: {trecho}",
                    "categoria": "Diário Oficial (Querido Diário)",
                    "link": link,
                }
            time.sleep(1)

        return list(resultados.values())

    _adaptador.__name__ = f"adaptador_qd_{_sem_acento(nome_cidade).replace(' ', '_')}"
    return _adaptador


def adaptador_sesa_seap_pr():
    """
    Concurso SESA/SEAP-PR — Edital nº 265/2025-DRH/SEAP (Médico, cadastro
    de reserva). A FAFIPA publica TODOS os editais/atos desse concurso
    numa única página (plataforma ProSeleta), então basta acompanhar essa
    página — sem precisar do Diário Oficial do Estado (que, aliás, migrou
    de plataforma em 13/07/2026 e está instável).

    Página oficial: https://www.fundacaofafipa.org.br/informacoes/4122/
    (usamos o espelho ps-adm-281.selecao.net.br, mesma plataforma, que
    responde sem bloqueio de robô).
    """
    NOME = "SESA/SEAP-PR (Edital 265/2025)"
    URL = "https://ps-adm-281.selecao.net.br/informacoes/4122/"

    def _adaptador():
        try:
            r = requests.get(URL, headers=HEADERS, timeout=25)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[{NOME}] erro na busca: {e}", file=sys.stderr)
            return []

        sopa = BeautifulSoup(r.text, "html.parser")
        resultados = {}
        for a in sopa.find_all("a", href=True):
            titulo = a.get_text(strip=True)
            href = a["href"]
            # os itens de publicação (Editais/Anexos/Resoluções) sempre
            # linkam pra um PDF hospedado em anexos*.selecao.net.br
            if not titulo or "selecao.net.br" not in href or "/anexos/" not in href:
                continue
            if not bate_palavra(titulo):
                continue

            m = re.search(r"(\d{2}/\d{2}/\d{4})", titulo)
            data = m.group(1) if m else ""

            resultados[href] = {
                "cidade": NOME,
                "data": data,
                "titulo": titulo,
                "categoria": "Edital/Resolução FAFIPA",
                "link": href,
            }
        return list(resultados.values())

def adaptador_cambe_pr():
    """
    Cambé-PR — Jornal Oficial do Município, WordPress com o plugin
    "WordPress Download Manager". Cada edição é um item de lista com link
    pra /index.php/download/edicao-N-DD-MM-AAAA[-titulo-do-destaque]/.

    Boa notícia: o TÍTULO do link já costuma trazer o resumo do destaque da
    edição quando há algo relevante (ex.: "Edição 1890 – 22.06.2026 - Edital
    de Resultado e Classificação Final do PSS nº 001/2026..."), então o
    bate_palavra já filtra bem sem precisar abrir o PDF.
    """
    NOME = "Cambé-PR"
    URL = "https://jornal.cambe.pr.gov.br/"

    def _adaptador():
        try:
            r = requests.get(URL, headers=HEADERS, timeout=25)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[{NOME}] erro na busca: {e}", file=sys.stderr)
            return []

        sopa = BeautifulSoup(r.text, "html.parser")
        resultados = {}
        for a in sopa.find_all("a", href=True):
            titulo = a.get_text(strip=True)
            href = a["href"]
            if "/index.php/download/" not in href or not titulo.lower().startswith("edição"):
                continue
            if not bate_palavra(titulo):
                continue

            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", titulo)
            data = f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ""

            resultados[href] = {
                "cidade": NOME,
                "data": data,
                "titulo": titulo,
                "categoria": "Jornal Oficial",
                "link": href,
            }
        return list(resultados.values())

    _adaptador.__name__ = "adaptador_cambe_pr"
    return _adaptador


# ---------------------------------------------------------------------------
# >>> SUAS CIDADES / CONCURSOS <<<  (registre aqui tudo que você acompanha)
# ---------------------------------------------------------------------------
CIDADES = [
    # Cidade que usa a plataforma padrão (URL com /filtrarDiarioSearch):
    adaptador_portal_padrao("Catanduvas-PR", "https://catanduvas.pr.gov.br"),

    # Cambé tem adaptador próprio (site direto, sem captcha nem bloqueio):
    adaptador_cambe_pr(),

    # Cidades via API do Querido Diário (ver observação de cobertura acima):
    criar_adaptador_querido_diario("Goioerê-PR", "4108601"),
    criar_adaptador_querido_diario("Prado Ferreira-PR", "4120333"),
    criar_adaptador_querido_diario("Marechal C. Rondon-PR", "4114609"),

    # Concurso estadual SESA/SEAP-PR (Edital 265/2025 — cadastro de reserva):
    adaptador_sesa_seap_pr(),

    # Para adicionar outra cidade da MESMA plataforma da Catanduvas, copie:
    # adaptador_portal_padrao("Outra Cidade-PR", "https://outracidade.pr.gov.br"),

    # Para cidade de plataforma DIFERENTE, escreva um adaptador próprio
    # (ver ADICIONAR-CIDADE.md) e registre o nome da função aqui, ex.:
    # adaptador_minhacidade,
]


# ===========================================================================
# NOTIFICAÇÃO — envia em todos os canais configurados
# ===========================================================================

def _monta_texto(novos):
    linhas = [f"🔔 {len(novos)} publicação(ões) nova(s) de concurso:\n"]
    for it in novos:
        linhas.append(f"• [{it['cidade']}] {it['data']} — {it['titulo']}")
        if it.get("link"):
            linhas.append(f"  {it['link']}")
    return "\n".join(linhas)


def _enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": texto, "disable_web_page_preview": "true"},
            timeout=15,
        )
        print("[telegram] enviado.")
    except requests.RequestException as e:
        print(f"[telegram] falha: {e}", file=sys.stderr)


def _enviar_email(texto):
    remetente = os.environ.get("EMAIL_REMETENTE")
    senha = os.environ.get("EMAIL_SENHA_APP")
    destino = os.environ.get("EMAIL_DESTINO")
    if not (remetente and senha and destino):
        return
    try:
        msg = MIMEText(texto, "plain", "utf-8")
        msg["Subject"] = "🔔 Concurso: nova publicação no Diário Oficial"
        msg["From"] = remetente
        msg["To"] = destino
        host = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
        porta = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        with smtplib.SMTP(host, porta, timeout=20) as s:
            s.starttls()
            s.login(remetente, senha)
            s.send_message(msg)
        print("[email] enviado.")
    except Exception as e:
        print(f"[email] falha: {e}", file=sys.stderr)


def _enviar_push(texto):
    """Push no celular via ntfy.sh (grátis, app nativo no iPhone)."""
    topico = os.environ.get("NTFY_TOPIC")
    if not topico:
        return
    servidor = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    try:
        requests.post(
            f"{servidor}/{topico}",
            data=texto.encode("utf-8"),
            headers={"Title": "Concurso: nova publicacao", "Priority": "high", "Tags": "rotating_light"},
            timeout=15,
        )
        print("[push/ntfy] enviado.")
    except requests.RequestException as e:
        print(f"[push/ntfy] falha: {e}", file=sys.stderr)


def notificar(novos):
    texto = _monta_texto(novos)
    print(texto)                 # sempre aparece no log do Actions
    _enviar_telegram(texto)      # cada um só dispara se estiver configurado
    _enviar_email(texto)
    _enviar_push(texto)


# ===========================================================================
# Estado (snapshot) + laço principal
# ===========================================================================

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"vistos": []}


def salvar_estado(chaves_vistas):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump({"vistos": sorted(chaves_vistas)}, f, ensure_ascii=False, indent=2)


def chave_do(item):
    return item["link"] or f'{item["cidade"]}|{item["data"]}|{item["titulo"]}'


def main():
    atuais = []
    for adaptador in CIDADES:
        try:
            atuais.extend(adaptador())
        except Exception as e:  # um adaptador quebrado não derruba os outros
            print(f"[{getattr(adaptador, '__name__', adaptador)}] erro: {e}", file=sys.stderr)

    estado = carregar_estado()
    vistos = set(estado.get("vistos", []))

    novos = [it for it in atuais if chave_do(it) not in vistos]

    if novos:
        notificar(novos)
    else:
        print("Nada novo desta vez.")

    # o snapshot acumula tudo que já foi visto (não só o desta rodada)
    for it in atuais:
        vistos.add(chave_do(it))
    salvar_estado(vistos)


if __name__ == "__main__":
    main()
