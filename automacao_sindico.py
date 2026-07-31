"""
Bot de Notícias Condominiais Profissional
-----------------------------------------
Busca notícias nas últimas 24h utilizando múltiplas palavras-chave no Google News,
agrega, remove duplicadas, ordena por data e envia para o Gemini selecionar as
mais relevantes de acordo com critérios investigativos rigorosos.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

# ---------- DEDUPLICAÇÃO ----------
JORNAL_DEDUP_JANELA_HORAS = int(os.environ.get("JORNAL_DEDUP_JANELA_HORAS") or 72)
JORNAL_DEDUP_ARQUIVO = Path(
    os.environ.get("JORNAL_DEDUP_ARQUIVO") or ".cache/noticias_enviadas.json"
)
JORNAL_DEDUP_HISTORICO_GEMINI = int(
    os.environ.get("JORNAL_DEDUP_HISTORICO_GEMINI") or 30
)

# ---------- PERFIS E BUSCAS ----------
PERFIS = {
    "condominios": {
        "titulo": "🏢 <b>Boletim de Inteligência Condominial</b> 🏢",
        "buscas": [
            "condominio", "condomínios", "síndico", "sindica", 
            "administração condominial", "gestão condominial", 
            "assembleia de condomínio", "taxa condominial", 
            "portaria remota", "segurança condominial", 
            "condomínio residencial", "condomínio comercial", 
            "mercado imobiliário", "manutenção predial", 
            "elevador", "incêndio condomínio", 
            "STJ condomínio", "decisão judicial condomínio", 
            "LGPD condomínio", "inteligência artificial condomínios"
        ],
        "persona": (
            "Você é um jornalista investigativo especializado no mercado condominial brasileiro. "
            "Possui experiência em administração de condomínios, direito condominial, gestão predial, "
            "mercado imobiliário, segurança, tecnologia e políticas públicas. "
            "Sua missão é identificar fatos realmente importantes, ignorando matérias superficiais, "
            "publicidade e conteúdos repetidos. "
            "Você sempre prioriza notícias que podem gerar impacto financeiro, jurídico, operacional "
            "ou estratégico para síndicos, administradoras e moradores."
        ),
        "criterio": (
            "Escolha exclusivamente as notícias que apresentem maior impacto para o setor condominial. "
            "Priorize: \n"
            "• mudanças na legislação;\n"
            "• decisões judiciais (STJ, STF, Tribunais);\n"
            "• crimes, fraudes e segurança;\n"
            "• incêndios e acidentes;\n"
            "• novas tecnologias e IA;\n"
            "• economia e aumento de tarifas;\n"
            "• inovação, sustentabilidade e mercado imobiliário.\n\n"
            "Desconsidere: publicidade, artigos de opinião, matérias promocionais, "
            "notícias sem impacto prático.\n"
            "Caso existam diversas matérias sobre o mesmo assunto, escolha apenas a de melhor fonte. "
            "É ESTRITAMENTE PROIBIDO escolher manchetes ou fatos que já tenham aparecido no bloco 'JÁ ENVIADAS'."
        ),
    },
    "energia": {
        "titulo": "⚡ <b>Radar de Energia</b> ⚡",
        "buscas": [
            "tarifa de energia", "ANEEL", "bandeira tarifária",
            "conta de luz", "reajuste energia elétrica",
            "energia solar", "geração distribuída",
        ],
        "persona": (
            "Você é um analista do setor elétrico brasileiro, especializado em "
            "tarifas, regulação da ANEEL e impacto dos custos de energia sobre "
            "consumidores, condomínios e empresas."
        ),
        "criterio": (
            "Escolha as notícias com maior impacto prático sobre tarifas, "
            "regulação e custos de energia. Priorize reajustes, decisões da ANEEL, "
            "mudanças de bandeira tarifária e novas regras. Desconsidere publicidade "
            "e conteúdo promocional. É ESTRITAMENTE PROIBIDO escolher manchetes ou "
            "fatos que já tenham aparecido no bloco 'JÁ ENVIADAS'."
        ),
    },
    "saneamento": {
        "titulo": "💧 <b>Radar de Saneamento</b> 💧",
        "buscas": [
            "saneamento básico", "tarifa de água", "abastecimento de água",
            "concessionária de água", "marco legal do saneamento",
            "esgotamento sanitário", "racionamento de água",
        ],
        "persona": (
            "Você é um analista do setor de saneamento brasileiro, especializado "
            "em tarifas de água, concessionárias e regulação do setor."
        ),
        "criterio": (
            "Escolha as notícias com maior impacto sobre tarifas, abastecimento "
            "e regulação do saneamento. Priorize reajustes, decisões regulatórias "
            "e mudanças que afetem consumidores e condomínios. Desconsidere "
            "publicidade. É ESTRITAMENTE PROIBIDO escolher manchetes ou fatos que "
            "já tenham aparecido no bloco 'JÁ ENVIADAS'."
        ),
    },
    "tecnologia": {
        "titulo": "🤖 <b>Radar de Tecnologia</b> 🤖",
        "buscas": [
            "inteligência artificial", "desenvolvimento de software",
            "segurança da informação", "automação", "startups Brasil",
        ],
        "persona": (
            "Você é um editor de tecnologia focado em IA, desenvolvimento de "
            "software e segurança da informação, com olhar prático para o que "
            "muda o dia a dia de quem trabalha com tecnologia."
        ),
        "criterio": (
            "Escolha as notícias mais relevantes sobre IA, ferramentas de "
            "desenvolvimento e segurança. Priorize lançamentos, vulnerabilidades "
            "e mudanças com efeito prático. Desconsidere publicidade e listas "
            "genéricas. É ESTRITAMENTE PROIBIDO escolher manchetes ou fatos que "
            "já tenham aparecido no bloco 'JÁ ENVIADAS'."
        ),
    },
    "local": {
        # Edite os termos de busca para a sua cidade/estado.
        "titulo": "📍 <b>Notícias da Região</b> 📍",
        "buscas": [
            "Recife", "Pernambuco",
        ],
        "persona": (
            "Você é um editor de jornal local, atento ao que realmente afeta o "
            "cotidiano dos moradores da região."
        ),
        "criterio": (
            "Escolha as notícias de maior interesse público local: serviços, "
            "obras, segurança, economia e decisões do poder público. Desconsidere "
            "notas policiais menores e publicidade. É ESTRITAMENTE PROIBIDO "
            "escolher manchetes ou fatos que já tenham aparecido no bloco "
            "'JÁ ENVIADAS'."
        ),
    },
    "concorrencia": {
        # Substitua pelos nomes das empresas que deseja monitorar.
        "titulo": "🔎 <b>Radar de Mercado</b> 🔎",
        "buscas": [
            '"nome da empresa 1"', '"nome da empresa 2"',
        ],
        "persona": (
            "Você é um analista de inteligência competitiva que monitora "
            "movimentos de empresas específicas do mercado."
        ),
        "criterio": (
            "Escolha as notícias que revelem movimentos relevantes das empresas "
            "monitoradas: lançamentos, contratos, expansão, problemas jurídicos "
            "ou financeiros. Desconsidere menções triviais. É ESTRITAMENTE "
            "PROIBIDO escolher manchetes ou fatos que já tenham aparecido no "
            "bloco 'JÁ ENVIADAS'."
        ),
    },
}

PERFIL_ATIVO = os.environ.get("PERFIL_ATIVO") or "condominios"
PERFIL = PERFIS.get(PERFIL_ATIVO)
if PERFIL is None:
    sys.exit(
        f"Erro: o perfil '{PERFIL_ATIVO}' não existe. "
        f"Perfis disponíveis: {', '.join(PERFIS)}"
    )

# ---------- COMPORTAMENTO ----------
QUANTIDADE_FINAL = 6
MAX_NOTICIAS_ANALISADAS = 50
LIMITE_TELEGRAM = 4096
RESOLVER_LINKS = True
TIMEOUT_RESOLUCAO = 8
MAX_TENTATIVAS_GEMINI = 4
ESPERA_INICIAL_GEMINI = 5

# ---------- FONTE ----------
IDIOMA = "pt-BR"
REGIAO = "BR"
EDICAO = "BR:pt-419"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# =================================================

# ============== DEDUPLICAÇÃO E CACHE ==============

def normalizar_para_hash(texto):
    return re.sub(r"\s+", " ", texto or "").strip().lower()

def hash_noticia(noticia):
    carga = f"{normalizar_para_hash(noticia['link'])}|{normalizar_para_hash(noticia['titulo'])}"
    return hashlib.sha256(carga.encode("utf-8")).hexdigest()

def carregar_cache():
    if not JORNAL_DEDUP_ARQUIVO.exists():
        return {"entries": []}
    try:
        with JORNAL_DEDUP_ARQUIVO.open("r", encoding="utf-8") as f:
            dados = json.load(f)
        if not isinstance(dados, dict) or "entries" not in dados:
            return {"entries": []}
        return dados
    except (json.JSONDecodeError, OSError) as erro:
        print(f"[dedup] cache ilegível ({erro}); partindo de cache vazio.")
        return {"entries": []}

def podar_cache(cache, agora=None):
    agora = agora or datetime.now(timezone.utc)
    limite = agora - timedelta(hours=JORNAL_DEDUP_JANELA_HORAS)
    antes = len(cache["entries"])
    cache["entries"] = [
        e for e in cache["entries"]
        if datetime.fromisoformat(e["enviado_em"]) >= limite
    ]
    removidas = antes - len(cache["entries"])
    if removidas:
        print(f"[dedup] {removidas} entradas expiraram (fora da janela).")

def ja_enviado(noticia, cache):
    h = hash_noticia(noticia)
    return any(e.get("hash") == h for e in cache["entries"])

def historico_para_prompt(cache):
    ordenadas = sorted(
        cache["entries"],
        key=lambda e: e["enviado_em"],
        reverse=True,
    )[:JORNAL_DEDUP_HISTORICO_GEMINI]
    return [html.escape(e["titulo"], quote=False) for e in ordenadas]

def registrar_envios(noticias, cache):
    agora_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for n in noticias:
        cache["entries"].append({
            "hash": hash_noticia(n),
            "titulo": n["titulo"],
            "link": n["link"],
            "enviado_em": agora_iso,
        })
    podar_cache(cache)

def gravar_cache(cache):
    JORNAL_DEDUP_ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = JORNAL_DEDUP_ARQUIVO.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    tmp.replace(JORNAL_DEDUP_ARQUIVO)

def resetar_cache():
    if JORNAL_DEDUP_ARQUIVO.exists():
        JORNAL_DEDUP_ARQUIVO.unlink()
        print(f"[dedup] cache removido: {JORNAL_DEDUP_ARQUIVO}")
    else:
        print("[dedup] cache já estava ausente; nada a remover.")

# ============== TELEGRAM / GEMINI / FLUXO ==============

def validar_config():
    obrigatorias = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    faltando = [nome for nome, valor in obrigatorias.items() if not valor]
    if faltando:
        print("Erro de configuração. Faltam as variáveis:")
        for nome in faltando:
            print(f"   - {nome}")
        sys.exit(1)

def buscar_noticias_condominiais(cache):
    print(f"1. Realizando múltiplas buscas no Google News [perfil: {PERFIL_ATIVO}]...")
    todas_candidatas = []
    links_vistos = set()

    # Itera sobre todas as consultas independentes
    for busca in PERFIL["buscas"]:
        url = (
            "https://news.google.com/rss/search"
            f"?q={quote(busca + ' when:1d')}&hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
        )
        feed = feedparser.parse(url)
        
        for entrada in feed.entries:
            link = entrada.link
            
            # Remove duplicadas exatas da busca (camada 1 de dedup da iteração)
            if link in links_vistos:
                continue
            links_vistos.add(link)

            fonte = ""
            if hasattr(entrada, "source") and hasattr(entrada.source, "title"):
                fonte = entrada.source.title

            # Extrai o timestamp para ordenar
            data_publicacao = 0
            if hasattr(entrada, "published_parsed") and entrada.published_parsed:
                data_publicacao = time.mktime(entrada.published_parsed)

            todas_candidatas.append({
                "titulo": entrada.title,
                "link": link,
                "fonte": fonte,
                "timestamp": data_publicacao
            })

    # Ordena as notícias da mais recente para a mais antiga
    todas_candidatas.sort(key=lambda x: x["timestamp"], reverse=True)

    # Remove duplicadas que já foram enviadas recentemente
    filtradas = [n for n in todas_candidatas if not ja_enviado(n, cache)]
    descartadas = len(todas_candidatas) - len(filtradas)
    
    print(
        f"-> {len(todas_candidatas)} notícias únicas encontradas no total; "
        f"{descartadas} descartadas por já constarem no cache."
    )
    
    # Retorna o top N (agora 40~50) para o Gemini analisar
    return filtradas[:MAX_NOTICIAS_ANALISADAS]

def resolver_link(link):
    if not RESOLVER_LINKS or "news.google.com" not in link:
        return link
    try:
        resposta = requests.get(
            link, headers={"User-Agent": USER_AGENT},
            allow_redirects=True, timeout=TIMEOUT_RESOLUCAO,
        )
    except requests.RequestException:
        return link

    if "news.google.com" not in resposta.url:
        return resposta.url

    match = re.search(r'data-n-au="([^"]+)"', resposta.text)
    if match:
        return html.unescape(match.group(1))

    match = re.search(r'<a[^>]+href="(https?://(?!news\.google)[^"]+)"', resposta.text)
    if match:
        return html.unescape(match.group(1))

    return link

def montar_prompt(noticias, cache):
    lista = "\n".join(
        f"{i + 1}. {n['titulo']}" + (f" [{n['fonte']}]" if n["fonte"] else "")
        for i, n in enumerate(noticias)
    )

    historico = historico_para_prompt(cache)
    bloco_historico = ""
    if historico:
        bloco_historico = (
            "JÁ ENVIADAS nas últimas "
            f"{JORNAL_DEDUP_JANELA_HORAS}h (NÃO repita estas manchetes, "
            "nem o mesmo fato por outro ângulo ou veículo):\n"
            + "\n".join(f"- {t}" for t in historico)
            + "\n\n"
        )

    return f"""
{PERFIL['persona']}

Analise a lista de manchetes abaixo e selecione as {QUANTIDADE_FINAL} notícias.
{PERFIL['criterio']}

{bloco_historico}Responda APENAS com um array JSON válido, sem markdown. 
Cada item deve conter EXATAMENTE as seguintes chaves:

  "numero"    - o número da notícia na lista (inteiro)
  "emoji"     - um único emoji visualmente relacionado ao tema (ex: ⚖️, 🏢, 🚨, 💰)
  "categoria" - palavra curta que defina o tema (ex: Jurídico, Segurança, Inovação, Mercado)
  "impacto"   - nota de 1 a 10 representando o grau de impacto no setor
  "motivo"    - uma frase curta e direta explicando a importância prática da notícia
  "publico"   - alvo primário (ex: Síndicos, Moradores, Administradoras)
  "urgencia"  - nível de urgência (Baixa, Média, Alta)

Formato esperado:
[
  {{
    "numero": 4,
    "emoji": "⚖️",
    "categoria": "Jurídico",
    "impacto": 10,
    "motivo": "Muda a responsabilidade civil do síndico em casos de inadimplência.",
    "publico": "Síndicos",
    "urgencia": "Alta"
  }}
]

Lista de manchetes de hoje (já filtradas):
{lista}
""".strip()

def extrair_texto(resposta):
    try:
        partes = resposta.candidates[0].content.parts
        texto = "".join(p.text for p in partes if getattr(p, "text", None))
        if texto.strip():
            return texto.strip()
    except (AttributeError, IndexError, TypeError):
        pass
    return (resposta.text or "").strip()

def parsear_json(texto):
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
    texto = str(erro)
    return any(
        marcador in texto
        for marcador in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
    )

def chamar_gemini_com_retentativa(client, prompt):
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
            print(f"-> Modelo sobrecarregado (tentativa {tentativa}/{MAX_TENTATIVAS_GEMINI}). Aguardando {espera}s...")
            time.sleep(espera)
            espera *= 2

def selecionar_com_ia(client, noticias, cache):
    print(f"2. Analisando {len(noticias)} notícias com o modelo {GEMINI_MODEL}...")
    resposta = chamar_gemini_com_retentativa(client, montar_prompt(noticias, cache))

    try:
        selecoes = parsear_json(extrair_texto(resposta))
    except ValueError as erro:
        print(f"-> Resposta inválida do Gemini: {erro}")
        return []

    escolhidas = []
    vistos = set()

    for item in selecoes:
        try:
            indice = int(item.get("numero", -1)) - 1
        except (KeyError, TypeError, ValueError):
            continue

        if indice < 0 or indice >= len(noticias) or indice in vistos:
            continue

        vistos.add(indice)
        noticia = noticias[indice]
        
        if ja_enviado(noticia, cache):
            continue
            
        escolhidas.append({
            "titulo": noticia["titulo"],
            "link": noticia["link"],
            "emoji": str(item.get("emoji", "📰"))[:4],
            "categoria": str(item.get("categoria", "Geral")),
            "impacto": item.get("impacto", 5),
            "motivo": str(item.get("motivo", "")).strip(),
            "publico": str(item.get("publico", "Geral")),
            "urgencia": str(item.get("urgencia", "Média"))
        })

    print(f"-> {len(escolhidas)} notícias selecionadas com sucesso.")
    return escolhidas[:QUANTIDADE_FINAL]

def montar_mensagem(escolhidas):
    print("3. Montando a mensagem com os novos metadados e resolvendo os links...")
    blocos = [PERFIL["titulo"] + "\n"]

    for noticia in escolhidas:
        link = resolver_link(noticia["link"])
        titulo = html.escape(noticia["titulo"], quote=False)
        motivo = html.escape(noticia["motivo"], quote=False)
        categoria = html.escape(noticia["categoria"], quote=False)
        publico = html.escape(noticia["publico"], quote=False)
        urgencia = html.escape(noticia["urgencia"], quote=False)
        url = html.escape(link, quote=True)

        bloco = f"{noticia['emoji']} <b>{titulo}</b>"
        bloco += f"\n🏷️ <i>{categoria}</i> | 🎯 <b>Público:</b> {publico} | 🚨 <b>Urgência:</b> {urgencia} | 💥 <b>Impacto:</b> {noticia['impacto']}/10"
        
        if motivo:
            bloco += f"\n{motivo}"
        bloco += f'\n<a href="{url}">Ler a matéria completa</a>'

        blocos.append(bloco)

    return "\n\n".join(blocos)

def dividir_mensagem(mensagem, limite=LIMITE_TELEGRAM):
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
    print("4. Enviando o resumo final de inteligência para o Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    sucesso_total = True

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
            sucesso_total = False
            break

        if resposta.status_code != 200:
            print(f"-> Erro ao enviar bloco: {resposta.text}")
            sucesso_total = False
            break

    if not sucesso_total:
        return False

    print("-> Boletim entregue com sucesso!")
    return True

# ============== MAIN ==============

def main():
    parser = argparse.ArgumentParser(description="Bot de inteligência condominial.")
    parser.add_argument("--resetar-cache", action="store_true")
    args = parser.parse_args()

    if args.resetar_cache:
        resetar_cache()

    validar_config()
    client = genai.Client(api_key=GEMINI_API_KEY)
    cache = carregar_cache()
    podar_cache(cache)

    try:
        noticias = buscar_noticias_condominiais(cache)
    except Exception as erro:
        print(f"Erro ao buscar as notícias: {erro}")
        sys.exit(1)

    if not noticias:
        print("Nenhuma notícia nova encontrada após as múltiplas buscas e filtragens de cache.")
        return

    try:
        escolhidas = selecionar_com_ia(client, noticias, cache)
    except Exception as erro:
        print(f"Erro na chamada ao Gemini: {erro}")
        sys.exit(1)

    if not escolhidas:
        print("O modelo não selecionou nenhuma notícia. Nada enviado.")
        return

    mensagem = montar_mensagem(escolhidas)
    if not enviar_telegram(mensagem):
        print("Falha no envio. O cache não foi atualizado.")
        sys.exit(1)

    registrar_envios(escolhidas, cache)
    gravar_cache(cache)
    print(f"[dedup] {len(escolhidas)} entradas gravadas em cache.")

if __name__ == "__main__":
    main()
