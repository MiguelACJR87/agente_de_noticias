"""
Bot de Notícias Condominiais
----------------------------
Busca notícias das últimas 24h no Google News, seleciona as mais
relevantes com o Gemini e envia o resumo para o Telegram.

Os links nunca passam pelo modelo: o Gemini devolve apenas o número
da notícia escolhida e o Python monta a mensagem com a URL original
do feed, evitando links truncados ou alterados.

Configuração:
    Copie o arquivo .env.example para .env e preencha os valores.
    O .env está no .gitignore e não vai para o repositório.

Uso:
    pip install -r requirements.txt
    python automacao_sindico.py
"""

import html
import json
import os
import re
import sys
import time
from urllib.parse import quote

import feedparser
import requests
from dotenv import load_dotenv
from google import genai

# Carrega o arquivo .env da pasta do projeto
load_dotenv()

# ================= CONFIGURAÇÕES =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash"

# ---------- PERFIS ----------
# Cada perfil define O QUE buscar, COMO julgar e COMO apresentar.
# Troque PERFIL_ATIVO para mudar completamente a finalidade do bot.
# Para criar o seu, copie um bloco abaixo e ajuste os quatro campos.

PERFIS = {
    "condominios": {
        "titulo": "🏢 <b>As Notícias Condominiais do Dia</b> 🏢",
        "busca": "condominio OR sindico when:1d",
        "persona": (
            "Você é um especialista do mercado imobiliário e gestão condominial."
        ),
        "criterio": "mais impactantes, urgentes ou relevantes para síndicos e moradores",
    },
    "energia": {
        "titulo": "⚡ <b>Radar do Setor Elétrico</b> ⚡",
        "busca": "tarifa energia OR ANEEL OR bandeira tarifaria when:1d",
        "persona": "Você é um analista do setor de energia elétrica brasileiro.",
        "criterio": (
            "mais relevantes para quem trabalha com medição e faturamento de energia"
        ),
    },
    "saneamento": {
        "titulo": "💧 <b>Radar de Saneamento</b> 💧",
        "busca": "tarifa agua OR saneamento OR COMPESA OR CAGEPA when:2d",
        "persona": "Você é um especialista em saneamento básico e regulação tarifária.",
        "criterio": "mais relevantes para gestão de consumo de água em condomínios",
    },
    "tecnologia": {
        "titulo": "💻 <b>Tech do Dia</b> 💻",
        "busca": "inteligencia artificial OR desenvolvimento de software when:1d",
        "persona": "Você é um engenheiro de software sênior acompanhando o mercado.",
        "criterio": "mais relevantes para quem desenvolve software profissionalmente",
    },
    "local": {
        "titulo": "📍 <b>Recife Hoje</b> 📍",
        "busca": "Recife OR Pernambuco when:1d",
        "persona": "Você é um jornalista local acompanhando a cidade.",
        "criterio": "de maior impacto no dia a dia de quem mora na região",
    },
    "concorrencia": {
        "titulo": "🔍 <b>Monitoramento de Mercado</b> 🔍",
        "busca": '"nome da empresa" OR "nome do concorrente" when:7d',
        "persona": "Você é um analista de inteligência de mercado.",
        "criterio": "com maior impacto competitivo ou reputacional",
    },
}

PERFIL_ATIVO = os.environ.get("PERFIL_ATIVO") or "condominios"
PERFIL = PERFIS[PERFIL_ATIVO]

# ---------- COMPORTAMENTO ----------
QUANTIDADE_FINAL = 6        # quantas notícias entram no resumo
MAX_NOTICIAS_ANALISADAS = 30  # quantas manchetes o modelo avalia
LIMITE_TELEGRAM = 4096
RESOLVER_LINKS = True       # converte o link do Google News na URL do veículo
TIMEOUT_RESOLUCAO = 8

# Nova tentativa automática quando o Gemini está sobrecarregado (erro 503)
# ou no limite de uso (erro 429). A espera dobra a cada tentativa: 5s, 10s, 20s.
MAX_TENTATIVAS_GEMINI = 4
ESPERA_INICIAL_GEMINI = 5  # segundos

# ---------- FONTE ----------
# Idioma e região do feed. Para notícias em inglês dos EUA:
#   IDIOMA="en-US", REGIAO="US", EDICAO="US:en"
IDIOMA = "pt-BR"
REGIAO = "BR"
EDICAO = "BR:pt-419"

URL_RSS = (
    "https://news.google.com/rss/search"
    f"?q={quote(PERFIL['busca'])}&hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# =================================================


def validar_config():
    """Falha cedo e com mensagem clara se faltar alguma credencial."""
    obrigatorias = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }

    faltando = [nome for nome, valor in obrigatorias.items() if not valor]
    if not faltando:
        return

    print("Erro de configuração. As seguintes variáveis não foram encontradas:")
    for nome in faltando:
        print(f"   - {nome}")
    print(
        "\nCopie o arquivo .env.example para .env e preencha os valores:\n"
        "   copy .env.example .env"
    )
    sys.exit(1)


def listar_modelos_disponiveis(client):
    """Mostra os modelos que a chave atual enxerga (útil quando dá 404)."""
    print("\nModelos disponíveis para a sua chave:")
    try:
        for modelo in client.models.list():
            print(f"   - {modelo.name}")
    except Exception as erro:
        print(f"   Não foi possível listar os modelos: {erro}")


def buscar_noticias_condominiais():
    print(f"1. Buscando notícias recentes [perfil: {PERFIL_ATIVO}]...")
    feed = feedparser.parse(URL_RSS)

    noticias = []
    for entrada in feed.entries[:MAX_NOTICIAS_ANALISADAS]:
        fonte = ""
        if hasattr(entrada, "source") and hasattr(entrada.source, "title"):
            fonte = entrada.source.title

        noticias.append(
            {
                "titulo": entrada.title,
                "link": entrada.link,
                "fonte": fonte,
            }
        )

    print(f"-> {len(noticias)} notícias encontradas.")
    return noticias


def resolver_link(link):
    """Segue o redirecionamento do Google News até a URL do veículo.

    Se não conseguir sair do domínio do Google, devolve o link original,
    que continua funcionando.
    """
    if not RESOLVER_LINKS or "news.google.com" not in link:
        return link

    try:
        resposta = requests.get(
            link,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            timeout=TIMEOUT_RESOLUCAO,
        )
    except requests.RequestException:
        return link

    if "news.google.com" not in resposta.url:
        return resposta.url

    # Alguns redirecionamentos vêm por JavaScript dentro do HTML
    match = re.search(r'data-n-au="([^"]+)"', resposta.text)
    if match:
        return html.unescape(match.group(1))

    match = re.search(r'<a[^>]+href="(https?://(?!news\.google)[^"]+)"', resposta.text)
    if match:
        return html.unescape(match.group(1))

    return link


def montar_prompt(noticias):
    lista = "\n".join(
        f"{i + 1}. {n['titulo']}" + (f" [{n['fonte']}]" if n["fonte"] else "")
        for i, n in enumerate(noticias)
    )

    return f"""
{PERFIL['persona']}
Analise a lista de manchetes abaixo e selecione as {QUANTIDADE_FINAL} notícias
{PERFIL['criterio']}.

Responda APENAS com um array JSON válido, sem markdown, sem crases,
sem nenhum texto antes ou depois. Cada item do array deve ter:

  "numero"  - o número da notícia na lista (inteiro)
  "emoji"   - um único emoji relacionado ao tema
  "motivo"  - uma frase curta explicando por que essa notícia importa

Formato esperado:
[{{"numero": 3, "emoji": "⚖️", "motivo": "Muda a responsabilidade do síndico em..."}}]

Não inclua links, títulos nem tags HTML na sua resposta.

Lista de manchetes de hoje:
{lista}
""".strip()


def extrair_texto(resposta):
    """Lê só as partes de texto, ignorando o thought_signature dos modelos 3.x."""
    try:
        partes = resposta.candidates[0].content.parts
        texto = "".join(p.text for p in partes if getattr(p, "text", None))
        if texto.strip():
            return texto.strip()
    except (AttributeError, IndexError, TypeError):
        pass

    return (resposta.text or "").strip()


def parsear_json(texto):
    """Extrai o array JSON mesmo se vier embrulhado em crases ou texto extra."""
    limpo = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()

    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", limpo, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("O modelo não devolveu um JSON válido.")


def eh_erro_temporario(erro):
    """503 (sobrecarga) e 429 (limite de uso) tendem a se resolver sozinhos
    em poucos segundos. Erros como 404 (modelo não existe) ou 401 (chave
    inválida) são permanentes — tentar de novo não muda o resultado, então
    esses continuam subindo na hora.
    """
    texto = str(erro)
    return any(
        marcador in texto
        for marcador in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
    )


def chamar_gemini_com_retentativa(client, prompt):
    """Chama o Gemini e tenta de novo automaticamente se o erro for temporário.

    Importante para execuções sem ninguém acompanhando (cron, GitHub Actions):
    sem isso, um pico de demanda bem na hora agendada derruba a execução do
    dia inteiro, sem chance de recuperação.
    """
    espera = ESPERA_INICIAL_GEMINI

    for tentativa in range(1, MAX_TENTATIVAS_GEMINI + 1):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        except Exception as erro:
            if not eh_erro_temporario(erro) or tentativa == MAX_TENTATIVAS_GEMINI:
                raise

            print(
                f"-> Modelo sobrecarregado (tentativa {tentativa}/"
                f"{MAX_TENTATIVAS_GEMINI}). Aguardando {espera}s..."
            )
            time.sleep(espera)
            espera *= 2


def selecionar_com_ia(client, noticias):
    print(f"2. Analisando as notícias com o Gemini ({GEMINI_MODEL})...")

    resposta = chamar_gemini_com_retentativa(client, montar_prompt(noticias))

    selecoes = parsear_json(extrair_texto(resposta))

    escolhidas = []
    vistos = set()

    for item in selecoes:
        try:
            indice = int(item["numero"]) - 1
        except (KeyError, TypeError, ValueError):
            continue

        if indice < 0 or indice >= len(noticias) or indice in vistos:
            continue

        vistos.add(indice)
        noticia = noticias[indice]
        escolhidas.append(
            {
                "titulo": noticia["titulo"],
                "link": noticia["link"],
                "emoji": str(item.get("emoji", "📰"))[:4],
                "motivo": str(item.get("motivo", "")).strip(),
            }
        )

    print(f"-> {len(escolhidas)} notícias selecionadas.")
    return escolhidas[:QUANTIDADE_FINAL]


def montar_mensagem(escolhidas):
    print("3. Montando a mensagem e resolvendo os links...")

    blocos = [PERFIL["titulo"] + "\n"]

    for noticia in escolhidas:
        link = resolver_link(noticia["link"])

        titulo = html.escape(noticia["titulo"], quote=False)
        motivo = html.escape(noticia["motivo"], quote=False)
        url = html.escape(link, quote=True)

        bloco = f"{noticia['emoji']} <b>{titulo}</b>"
        if motivo:
            bloco += f"\n{motivo}"
        bloco += f'\n<a href="{url}">Ler a notícia</a>'

        blocos.append(bloco)

    return "\n\n".join(blocos)


def dividir_mensagem(mensagem, limite=LIMITE_TELEGRAM):
    """Quebra a mensagem em blocos, respeitando as linhas em branco."""
    if len(mensagem) <= limite:
        return [mensagem]

    partes = []
    atual = ""

    for bloco in mensagem.split("\n\n"):
        if len(atual) + len(bloco) + 2 > limite:
            if atual:
                partes.append(atual.strip())
            atual = bloco + "\n\n"
        else:
            atual += bloco + "\n\n"

    if atual.strip():
        partes.append(atual.strip())

    return partes


def enviar_telegram(mensagem):
    print("4. Enviando o resumo final para o Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for indice, bloco in enumerate(dividir_mensagem(mensagem), start=1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": bloco,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resposta = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as erro:
            print(f"-> Falha de conexão com o Telegram: {erro}")
            return False

        if resposta.status_code != 200:
            print(f"-> Erro ao enviar o bloco {indice}: {resposta.text}")
            return False

    print("-> Mensagem entregue com sucesso no seu celular!")
    return True


def main():
    validar_config()
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        noticias = buscar_noticias_condominiais()
    except Exception as erro:
        print(f"Erro ao buscar as notícias: {erro}")
        return

    if not noticias:
        print("O mercado condominial está tranquilo hoje. Nenhuma notícia nova.")
        return

    try:
        escolhidas = selecionar_com_ia(client, noticias)
    except Exception as erro:
        print(f"Erro na chamada ao Gemini: {erro}")
        if "NOT_FOUND" in str(erro) or "404" in str(erro):
            print(f"\nO modelo '{GEMINI_MODEL}' não está disponível para a sua chave.")
            listar_modelos_disponiveis(client)
            print("\nAjuste GEMINI_MODEL no .env com um dos nomes acima.")
        elif eh_erro_temporario(erro):
            print(
                f"\nO Gemini seguiu sobrecarregado mesmo após "
                f"{MAX_TENTATIVAS_GEMINI} tentativas. Isso costuma passar "
                "em poucos minutos — rode o script de novo daqui a pouco."
            )
        return

    if not escolhidas:
        print("O modelo não selecionou nenhuma notícia válida. Nada a enviar.")
        return

    enviar_telegram(montar_mensagem(escolhidas))


if __name__ == "__main__":
    main()