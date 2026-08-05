# Bot de Notícias com Curadoria por IA

Motor de monitoramento em Python que coleta notícias de múltiplas buscas no
Google News, remove o que já foi enviado nos últimos dias, usa a API do Gemini
para selecionar as mais relevantes segundo um critério que você define, e
entrega um boletim formatado no Telegram.

Nasceu como um bot de notícias condominiais, mas o comportamento inteiro é
definido por **perfis** — o mesmo motor serve para monitorar tarifas de
energia, saneamento, tecnologia, notícias locais ou movimentos de
concorrentes.

```
┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌──────────┐   ┌──────────┐
│  FONTES  │ → │   DEDUP    │ → │  CURADORIA  │ → │ MONTAGEM │ → │  ENTREGA │
│ RSS multi│   │ (cache 72h)│   │   (Gemini)  │   │ (Python) │   │(Telegram)│
└──────────┘   └────────────┘   └─────────────┘   └──────────┘   └──────────┘
  trocáveis      não repete       critério          links do        canal
                 o já enviado     definido          feed puro       trocável
```

---

## Índice

- [Instalação](#instalação)
- [Configurar o Telegram (passo a passo)](#configurar-o-telegram-passo-a-passo)
- [Configurar a API do Gemini](#configurar-a-api-do-gemini)
- [Primeira execução](#primeira-execução)
- [Perfis: adaptando para outras finalidades](#perfis-adaptando-para-outras-finalidades)
- [Deduplicação: por que o bot não se repete](#deduplicação-por-que-o-bot-não-se-repete)
- [Dominando a busca do Google News](#dominando-a-busca-do-google-news)
- [Trocando a fonte: outros feeds e scraping](#trocando-a-fonte-outros-feeds-e-scraping)
- [Agendamento](#agendamento)
- [Decisões técnicas](#decisões-técnicas)
- [Solução de problemas](#solução-de-problemas)

---

## Instalação

Requer Python 3.9 ou superior.

```bash
git clone https://github.com/MiguelACJR87/agente_de_noticias.git
cd agente_de_noticias
pip install -r requirements.txt
```

---

## Configurar o Telegram (passo a passo)

Você precisa de duas informações: o **token do bot** (a identidade de quem
envia) e o **chat ID** (o endereço de quem recebe). São coisas diferentes, e a
confusão entre as duas é o erro mais comum.

### Etapa 1 — Criar o bot e obter o token

**1.** Abra o Telegram e busque por `@BotFather` na barra de pesquisa. A conta
oficial tem um selo azul de verificação ao lado do nome. Existem imitações —
confira o selo.

**2.** Abra a conversa e toque em **Iniciar** (ou envie `/start`).

**3.** Envie o comando:

```
/newbot
```

**4.** O BotFather vai pedir o **nome de exibição**. É o que aparece no topo
da conversa, pode ter espaços e acentos:

```
Radar Condominial
```

**5.** Agora ele pede o **username**. Este precisa ser único no Telegram
inteiro e **obrigatoriamente terminar em `bot`**:

```
radar_condominial_bot
```

Se o nome já existir, ele avisa e você tenta outro. Acrescentar números ou seu
identificador costuma resolver.

**6.** Deu certo? O BotFather responde com uma mensagem contendo uma linha
parecida com esta:

```
Use this token to access the HTTP API:
7891234567:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

Esse é o seu `TELEGRAM_BOT_TOKEN`. Copie inteiro, **incluindo os dois pontos**
e tudo que vem depois.

> ⚠️ Quem tem esse token controla o seu bot. Nunca coloque em código, captura
> de tela ou repositório. Se vazar, envie `/revoke` ao BotFather para
> invalidar o antigo e gerar um novo.

### Etapa 2 — Descobrir o chat ID

Um detalhe importante da API do Telegram: **um bot só consegue enviar mensagem
para quem já falou com ele antes**. Ele não pode iniciar conversa. Por isso o
primeiro passo é sempre você mandar uma mensagem.

#### Para receber no seu chat privado

**1.** Busque o username do seu bot no Telegram (o `@radar_condominial_bot` do
exemplo).

**2.** Abra e toque em **Iniciar**. Isso registra a conversa.

**3.** Abra esta URL no navegador, substituindo `<TOKEN>` pelo seu token:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Note que o `bot` faz parte da URL e cola direto no token, sem espaço nem
barra. Fica assim:

```
https://api.telegram.org/bot7891234567:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/getUpdates
```

**4.** Você vai ver um JSON. Procure pelo trecho `"chat"`:

```json
{
  "message": {
    "chat": {
      "id": 936478817,
      "first_name": "Miguel",
      "type": "private"
    }
  }
}
```

O número em `"id"` é o seu `TELEGRAM_CHAT_ID`.

> Se o retorno vier `{"ok":true,"result":[]}`, a mensagem do passo 2 não foi
> registrada. Mande qualquer coisa para o bot e recarregue a página.

#### Para receber em um grupo

**1.** Crie o grupo (ou use um existente).

**2.** Toque no nome do grupo → **Adicionar membros** → busque o username do
seu bot e adicione.

**3.** Envie qualquer mensagem no grupo.

**4.** Acesse a mesma URL `getUpdates` e procure o `"chat"` com
`"type": "group"` ou `"supergroup"`.

**IDs de grupo são negativos**, no formato `-1001234567890`. O sinal de menos
faz parte do ID — copie ele junto.

> Se o `getUpdates` não mostrar o grupo, o modo privacidade do bot está
> bloqueando a leitura. Envie `/setprivacy` ao BotFather, escolha o seu bot e
> selecione **Disable**. Depois mande outra mensagem no grupo e tente de novo.

#### Para publicar em um canal

**1.** Nas configurações do canal, adicione o bot como **administrador** com
permissão de publicar mensagens.

**2.** O ID do canal também é negativo. Você pode obtê-lo pelo `getUpdates`
após uma publicação, ou usar o identificador público diretamente:

```
TELEGRAM_CHAT_ID=@nome_do_seu_canal
```

### Etapa 3 — Personalizar o bot (opcional)

Ainda no BotFather, alguns comandos deixam o bot com cara de produto:

| Comando           | O que faz                                        |
| ----------------- | ------------------------------------------------ |
| `/setdescription` | Texto exibido antes de alguém iniciar a conversa |
| `/setabouttext`   | Descrição curta no perfil do bot                 |
| `/setuserpic`     | Define a foto de perfil                          |
| `/setcommands`    | Cadastra o menu de comandos                      |

---

## Configurar a API do Gemini

**1.** Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
e faça login com sua conta Google.

**2.** Clique em **Create API key** e selecione um projeto (ou deixe criar um
novo automaticamente).

**3.** Copie a chave gerada. Ela aparece uma única vez de forma completa.

O plano gratuito do AI Studio tem cota diária suficiente — este bot faz
**uma única chamada** ao modelo por execução.

---

## Primeira execução

Copie o arquivo de exemplo e preencha:

```bash
# Windows
copy .env.example .env
notepad .env

# Linux / macOS
cp .env.example .env
nano .env
```

Preencha assim:

```
GEMINI_API_KEY=AIzaSyD...
TELEGRAM_BOT_TOKEN=7891234567:AAHdq...
TELEGRAM_CHAT_ID=936478817
GEMINI_MODEL=
PERFIL_ATIVO=
```

Os demais campos podem ficar vazios — o script usa os padrões
(`gemini-3.6-flash` e o perfil `condominios`).

Rode:

```bash
python automacao_sindico.py
```

Saída esperada:

```
1. Realizando múltiplas buscas no Google News [perfil: condominios]...
-> 87 notícias únicas encontradas no total; 12 descartadas por já constarem no cache.
2. Analisando 50 notícias com o modelo gemini-3.6-flash...
-> 6 notícias selecionadas com sucesso.
3. Montando a mensagem com os novos metadados e resolvendo os links...
4. Enviando o resumo final de inteligência para o Telegram...
-> Boletim entregue com sucesso!
[dedup] 6 entradas gravadas em cache.
```

> O arquivo `.env` está no `.gitignore` e não vai para o repositório. O mesmo
> vale para a pasta `.cache/`, criada automaticamente na primeira execução.

---

## Perfis: adaptando para outras finalidades

Aqui está o coração do projeto. O comportamento inteiro é definido por um
**perfil** — um bloco de quatro campos no dicionário `PERFIS`, no topo do
script.

```python
"energia": {
    "titulo": "⚡ <b>Radar de Energia</b> ⚡",
    "buscas": [
        "tarifa de energia", "ANEEL", "bandeira tarifária",
        "conta de luz", "reajuste energia elétrica",
    ],
    "persona": "Você é um analista do setor elétrico brasileiro...",
    "criterio": "Escolha as notícias com maior impacto prático sobre tarifas...",
},
```

| Campo      | Função                                                                  |
| ---------- | ----------------------------------------------------------------------- |
| `titulo`   | Cabeçalho da mensagem no Telegram. Aceita as tags `<b>` e `<i>`         |
| `buscas`   | **Lista** de consultas independentes ao Google News. Define o que entra |
| `persona`  | Quem o modelo "é" ao julgar. Define a lente da análise                  |
| `criterio` | O que torna uma notícia relevante. Define o que sai do funil            |

Cada item de `buscas` vira uma consulta separada ao Google News (com a janela
`when:1d` acrescentada automaticamente pelo script). Os resultados de todas as
buscas são agregados, deduplicados por link e ordenados do mais recente para o
mais antigo antes de irem ao modelo.

Trocar de finalidade é trocar uma linha no `.env`:

```
PERFIL_ATIVO=energia
```

### Perfis já incluídos

| Perfil         | Monitora                                                       |
| -------------- | -------------------------------------------------------------- |
| `condominios`  | Gestão condominial, legislação, decisões judiciais, segurança  |
| `energia`      | Tarifas, ANEEL, bandeiras tarifárias, energia solar            |
| `saneamento`   | Água, esgoto, concessionárias, marco legal do saneamento       |
| `tecnologia`   | IA, desenvolvimento de software, segurança da informação       |
| `local`        | Notícias de uma cidade ou estado (edite os termos de busca)    |
| `concorrencia` | Menções a empresas específicas (substitua os nomes de exemplo) |

Os perfis `local` e `concorrencia` são modelos: abra o script e troque os
termos da lista `buscas` pelos seus.

### Criando o seu

Copie qualquer bloco e ajuste os quatro campos. Exemplo para monitorar
oportunidades públicas:

```python
"licitacoes": {
    "titulo": "📋 <b>Radar de Licitações</b> 📋",
    "buscas": ["licitacao", "pregao eletronico", "edital"],
    "persona": "Você é um analista comercial especializado em vendas para o setor público.",
    "criterio": (
        "Escolha as notícias que representam oportunidades reais de negócio "
        "para prestadores de serviço. É ESTRITAMENTE PROIBIDO escolher "
        "manchetes que já tenham aparecido no bloco 'JÁ ENVIADAS'."
    ),
},
```

**A `persona` importa mais do que parece.** A mesma notícia sobre reajuste
tarifário é lida de forma diferente por um "analista financeiro" e por um
"defensor do consumidor". Trocar essa frase muda quais notícias sobem no
ranking e como o motivo é escrito.

### Ajustes de volume e ritmo

```python
QUANTIDADE_FINAL = 6          # quantas notícias entram no resumo
MAX_NOTICIAS_ANALISADAS = 50  # quantas manchetes o modelo avalia
```

Aumentar `MAX_NOTICIAS_ANALISADAS` dá mais material para o modelo escolher, ao
custo de um prompt maior. Para nichos com pouco volume, prefira adicionar mais
termos à lista `buscas` do perfil.

### Mudando o formato da saída

O JSON pedido ao modelo já inclui, para cada notícia: `emoji`, `categoria`,
`impacto` (nota de 1 a 10), `motivo`, `publico` e `urgencia`. Para adicionar
um campo novo, inclua-o na especificação dentro de `montar_prompt()`, propague
no loop de `selecionar_com_ia()` e use em `montar_mensagem()`.

### Trocando o canal de entrega

A função `enviar_telegram()` é o único ponto acoplado ao Telegram. Para enviar
por e-mail, Discord, Slack ou webhook, substitua apenas ela — o resto do
pipeline não muda.

```python
def enviar_discord(mensagem):
    requests.post(WEBHOOK_URL, json={"content": mensagem}, timeout=30)
```

> Cada canal tem sua própria sintaxe de formatação. O Discord usa markdown,
> não HTML — ajuste a `montar_mensagem()` de acordo.

---

## Deduplicação: por que o bot não se repete

Rodando mais de uma vez por dia, o mesmo fato tende a reaparecer — no mesmo
link ou requentado por outro veículo. O bot combate isso em três camadas:

**1. Dedup por link na coleta.** Buscas diferentes retornam matérias
repetidas; a agregação descarta links já vistos na mesma execução.

**2. Cache persistente de envios.** Cada notícia enviada é registrada em
`.cache/noticias_enviadas.json` com um hash de link+título. Nas execuções
seguintes, tudo que está no cache é filtrado antes mesmo de chegar ao modelo.
As entradas expiram após a janela configurada (72h por padrão).

**3. Bloco "JÁ ENVIADAS" no prompt.** Os títulos mais recentes do cache são
mostrados ao Gemini com a instrução de não repetir o mesmo fato nem por outro
ângulo ou veículo — cobrindo o caso em que o link é novo mas a notícia não é.

Configuração pelo `.env` (todas opcionais):

```
JORNAL_DEDUP_JANELA_HORAS=72
JORNAL_DEDUP_ARQUIVO=.cache/noticias_enviadas.json
JORNAL_DEDUP_HISTORICO_GEMINI=30
```

Para zerar o histórico e recomeçar:

```bash
python automacao_sindico.py --resetar-cache
```

> No GitHub Actions o runner é descartado após cada execução — o cache só
> persiste lá porque o workflow restaura e salva a pasta `.cache` com
> `actions/cache`. Veja a seção [Agendamento](#agendamento).

---

## Dominando a busca do Google News

Cada item da lista `buscas` aceita operadores que refinam bastante o
resultado. A janela `when:1d` é acrescentada automaticamente pelo script — não
inclua `when:` nos seus termos (para mudar a janela, edite a montagem da URL
em `buscar_noticias_condominiais()`).

| Operador     | Efeito                   | Exemplo                     |
| ------------ | ------------------------ | --------------------------- |
| `OR`         | Qualquer um dos termos   | `condominio OR sindico`     |
| `"aspas"`    | Expressão exata          | `"convenção de condomínio"` |
| `-`          | Exclui o termo           | `energia -futebol`          |
| `site:`      | Restringe a um domínio   | `site:g1.globo.com`         |
| `intitle:`   | Só no título da matéria  | `intitle:tarifa`            |
| `allintext:` | Todos os termos no corpo | `allintext:sindico multa`   |

Combinando:

```python
"buscas": ['"gestão condominial" -futebol', "intitle:sindico"],
```

### Idioma e região

Três constantes controlam a edição do Google News:

```python
IDIOMA = "pt-BR"
REGIAO = "BR"
EDICAO = "BR:pt-419"
```

Para notícias em inglês dos Estados Unidos:

```python
IDIOMA = "en-US"
REGIAO = "US"
EDICAO = "US:en"
```

Isso muda quais veículos aparecem — não apenas o idioma. Útil para monitorar
tendências internacionais antes de chegarem ao Brasil.

### Feeds temáticos e geográficos

Além da busca, o Google News expõe feeds prontos. Para usá-los, substitua a
montagem da URL:

```python
# Por tópico: BUSINESS, TECHNOLOGY, SCIENCE, HEALTH, SPORTS, ENTERTAINMENT
url = (
    f"https://news.google.com/rss/headlines/section/topic/TECHNOLOGY"
    f"?hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
)

# Por localidade
url = (
    f"https://news.google.com/rss/headlines/section/geo/Recife"
    f"?hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
)
```

---

## Trocando a fonte: outros feeds e scraping

O Google News é o padrão por conveniência, mas a arquitetura não depende dele.
Qualquer função que devolva uma lista de dicionários com `titulo`, `link`,
`fonte` e `timestamp` pode substituir a `buscar_noticias_condominiais()`.

### Ordem de preferência das fontes

Antes de escrever um scraper, verifique se existe opção mais estável. Do mais
para o menos recomendável:

1. **API oficial** — contrato estável, documentado, autorizado
2. **Feed RSS/Atom** — estruturado, leve, publicado para ser consumido
3. **Sitemap XML** — muitos sites expõem `/sitemap.xml` ou `/news-sitemap.xml`
4. **Scraping do HTML** — último recurso, frágil, quebra a cada redesign

Boa parte dos portais brasileiros ainda publica RSS mesmo sem divulgar. Vale
testar `/feed`, `/rss`, `/rss.xml` ou `/feed/atom` na raiz do domínio antes de
partir para o HTML.

### Combinando múltiplos feeds RSS

```python
FEEDS = [
    "https://www.sindiconet.com.br/feed",
    "https://exemplo.com.br/categoria/condominios/feed",
]

for url in FEEDS:
    feed = feedparser.parse(url)
    origem = feed.feed.get("title", "")

    for entrada in feed.entries[:15]:
        if entrada.link in links_vistos:
            continue
        links_vistos.add(entrada.link)
        # monte o dicionário como no loop original
```

A deduplicação por link é essencial aqui — a mesma matéria costuma aparecer em
vários agregadores.

### Scraping de HTML

Quando não há feed, o `BeautifulSoup` resolve. Instale com:

```bash
pip install beautifulsoup4
```

Estrutura de um coletor:

```python
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def buscar_via_scraping(url_base, seletor):
    """Extrai manchetes de uma página HTML.

    seletor: seletor CSS que aponta para os links das matérias,
             ex.: 'h2.titulo a' ou 'article a.headline'
    """
    resposta = requests.get(
        url_base,
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resposta.raise_for_status()

    sopa = BeautifulSoup(resposta.text, "html.parser")
    noticias = []

    for elemento in sopa.select(seletor):
        titulo = elemento.get_text(strip=True)
        href = elemento.get("href", "")

        if not titulo or not href:
            continue

        noticias.append({
            "titulo": titulo,
            "link": urljoin(url_base, href),  # resolve links relativos
            "fonte": url_base,
            "timestamp": 0,
        })

    return noticias
```

Para descobrir o seletor: abra a página, clique com o botão direito sobre uma
manchete → **Inspecionar**. Olhe as classes CSS do elemento e dos pais dele.

### Páginas com conteúdo carregado por JavaScript

Se `resposta.text` vier sem as manchetes, o conteúdo é montado no navegador.
Duas saídas:

**Procure a API interna.** Abra o DevTools → aba **Network** → filtro
**Fetch/XHR** → recarregue a página. Frequentemente existe um endpoint JSON
que alimenta a tela. Consumir esse endpoint é mais rápido e mais estável do
que qualquer scraping de HTML.

**Use um navegador headless**, se não houver alternativa:

```bash
pip install playwright
playwright install chromium
```

```python
from playwright.sync_api import sync_playwright

def buscar_com_js(url, seletor):
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(url, wait_until="networkidle")
        html = pagina.content()
        navegador.close()
    return BeautifulSoup(html, "html.parser").select(seletor)
```

Custa muito mais recurso. Use só quando as outras opções falharem.

### Boas práticas — leia antes de coletar

Scraping mal feito derruba site pequeno e queima seu IP. O básico:

**Consulte o `robots.txt`.** Está sempre em `dominio.com.br/robots.txt` e
lista os caminhos que o site pede para não serem varridos. Respeite.

```python
from urllib.robotparser import RobotFileParser

def pode_coletar(url, user_agent="*"):
    parser = RobotFileParser()
    parser.set_url(urljoin(url, "/robots.txt"))
    parser.read()
    return parser.can_fetch(user_agent, url)
```

**Verifique os Termos de Uso.** Alguns sites proíbem coleta automatizada
independentemente do `robots.txt`. Reproduzir conteúdo integral também esbarra
em direito autoral — por isso este projeto trabalha só com **título e link**,
que é o que um agregador legitimamente faz.

**Espace as requisições.** Um `time.sleep(2)` entre páginas é o mínimo. Sem
isso você gera picos de carga que parecem ataque.

**Identifique-se.** Um User-Agent honesto com forma de contato é cortesia e
evita bloqueios.

**Cacheie durante o desenvolvimento.** Enquanto você ajusta os seletores,
salve o HTML em disco e trabalhe sobre o arquivo.

**Falhe com elegância.** Sites mudam. Envolva a coleta em `try/except` e trate
lista vazia como situação normal, não como erro fatal.

---

## Agendamento

### GitHub Actions (recomendado)

Roda na nuvem, sem depender da sua máquina. O workflow está em
`.github/workflows/diario.yml`:

```yaml
name: Resumo diário de notícias

on:
  schedule:
    - cron: "0 11 * * *"   # 08h em Brasília
    - cron: "0 15 * * *"   # 12h em Brasília
    - cron: "0 19 * * *"   # 16h em Brasília
  workflow_dispatch:

jobs:
  enviar-resumo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      # Persiste a pasta .cache entre execuções (o runner é efêmero).
      # A chave é única por execução porque o GitHub não sobrescreve
      # um cache existente; o restore-keys recupera o mais recente.
      - uses: actions/cache@v4
        with:
          path: .cache
          key: dedup-${{ github.run_id }}
          restore-keys: |
            dedup-

      - run: pip install -r requirements.txt
      - run: python automacao_sindico.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GEMINI_MODEL: gemini-3.6-flash
          PERFIL_ATIVO: condominios
```

As credenciais vão em **Settings → Secrets and variables → Actions → New
repository secret**. Nunca no arquivo YAML.

Pontos importantes:

- **Os horários do cron são em UTC.** Brasília é UTC−3, então `0 11 * * *`
  roda às 8h locais.
- **O passo `actions/cache` é o que faz a deduplicação funcionar na nuvem.**
  Sem ele, cada execução começa com o cache vazio e as notícias se repetem
  entre os horários do dia.
- **O GitHub desativa agendamentos após 60 dias sem atividade** em
  repositórios públicos. Chega um e-mail avisando; qualquer commit ou a
  reativação manual na aba Actions resolve.
- Para validar sem esperar o cron, use **Actions → Resumo diário de notícias
  → Run workflow**.
- Para rodar vários perfis, duplique o passo final com um `PERFIL_ATIVO`
  diferente.

### Windows — Agendador de Tarefas

**1.** Abra o menu Iniciar e busque por **Agendador de Tarefas**.

**2.** No painel direito, clique em **Criar Tarefa Básica**.

**3.** Nome: `Bot Notícias`. Avance.

**4.** Disparador: **Diariamente**. Defina o horário (ex.: 07:00).

**5.** Ação: **Iniciar um programa**.

**6.** Preencha:

| Campo      | Valor                                                |
| ---------- | ---------------------------------------------------- |
| Programa   | `C:\Users\SEU_USUARIO\anaconda3\python.exe`          |
| Argumentos | `automacao_sindico.py`                               |
| Iniciar em | `C:\Users\SEU_USUARIO\Desktop\Projetos\bot_noticias` |

O campo **Iniciar em** é obrigatório — sem ele o script não encontra o `.env`.

Para descobrir o caminho do seu Python:

```
where python
```

### Linux / macOS — cron

```bash
crontab -e
```

Adicione (todo dia às 7h):

```
0 7 * * * cd /caminho/do/projeto && /usr/bin/python3 automacao_sindico.py >> log.txt 2>&1
```

---

## Decisões técnicas

Notas de estudo sobre os problemas encontrados durante o desenvolvimento e o
raciocínio por trás de cada solução.

### Os links não passam pelo modelo

**Problema.** Na primeira versão, o prompt enviava título + link ao Gemini e
pedia a mensagem já formatada de volta. Os links chegavam quebrados no
Telegram.

**Causa.** As URLs do RSS do Google News são strings base64 de 200+
caracteres. Um LLM não copia isso de forma confiável — ele trunca, altera um
caractere ou completa o padrão de memória. O resultado parece uma URL válida,
mas não é.

**Solução.** Inverter a responsabilidade. O modelo devolve apenas um JSON com
o *índice* da notícia escolhida, e o Python remonta a mensagem usando o link
original do `feedparser`. Dado que não passa pelo modelo não pode ser
corrompido por ele.

> Princípio geral: use o LLM para julgamento, não para transporte de dados.

### Saída estruturada em vez de texto livre

Pedir JSON em vez de texto formatado trouxe validação de graça. Se o modelo
inventa um índice fora da lista ou repete uma notícia, o item é descartado no
loop de validação em vez de virar uma mensagem estranha. O parser também
tolera crases de markdown e texto extra ao redor do JSON, porque isso acontece
na prática.

### Configuração por perfis

Os quatro campos de um perfil isolam tudo que muda entre finalidades. A
alternativa seria espalhar strings pelo código e duplicar o script para cada
uso — o que multiplica a manutenção. Com perfis, corrigir um bug beneficia
todas as finalidades de uma vez.

### Deduplicação em três camadas

Com múltiplas buscas por execução e múltiplas execuções por dia, a repetição
deixou de ser exceção e virou o caso comum. O hash de link+título em cache
resolve a repetição exata; o bloco "JÁ ENVIADAS" no prompt resolve a
repetição semântica (mesmo fato, outro veículo). O cache é gravado de forma
atômica (arquivo temporário + `replace`) e só é atualizado **depois** do
envio bem-sucedido ao Telegram — falha no envio não "queima" as notícias.

### Sanitização antes do Telegram

O `parse_mode="HTML"` do Telegram aceita um conjunto restrito de tags e
devolve erro 400 se encontrar qualquer outra — ou um `<` solto no meio de um
título. Todo conteúdo dinâmico passa por `html.escape()` antes de ser inserido
na mensagem.

### Resolução dos links do Google News

Os links do feed são redirecionamentos. A função `resolver_link()` tenta
chegar à URL real do veículo em três etapas (redirecionamento HTTP, atributo
`data-n-au`, primeiro link externo do HTML) e, se todas falharem, devolve o
link original — que continua funcionando. Degradação graciosa em vez de erro.

### Modelos do Gemini mudam de nome

A versão inicial usava `gemini-1.5-flash-latest` e passou a retornar 404
quando a família 1.5 foi descontinuada. O modelo agora é configurável pela
variável de ambiente `GEMINI_MODEL`, sem alterar o código — tanto no `.env`
local quanto no workflow do Actions.

### Nova tentativa automática para erros temporários do Gemini

**Problema.** A API do Gemini eventualmente devolve `503 UNAVAILABLE` quando o
modelo está com pico de demanda — algo fora do controle do script. Sem
tratamento, isso derruba a execução, inclusive as agendadas, onde ninguém
está por perto para simplesmente rodar de novo.

**Solução.** `chamar_gemini_com_retentativa()` distingue erros temporários
(503, 429) de erros permanentes (404, chave inválida) e só insiste nos
primeiros, com espera crescente entre tentativas (5s, 10s, 20s). Um erro
permanente sobe na hora — tentar de novo não mudaria o resultado, só
atrasaria o diagnóstico.

### Códigos de saída honestos

Erros de busca, de Gemini ou de envio terminam com `sys.exit(1)`. No GitHub
Actions isso marca a execução com ❌ e dispara a notificação de falha — sem
isso, o workflow ficaria verde mesmo quebrado e ninguém saberia. "Nenhuma
notícia nova" continua saindo com código 0: é uma situação normal, não um
erro.

### Credenciais fora do código

Chave de API e token de bot ficam em `.env`, carregado por `python-dotenv` e
ignorado pelo Git. O `.env.example` documenta quais variáveis existem sem
revelar valores. No Actions, as mesmas variáveis vêm dos Secrets do
repositório. A função `validar_config()` falha logo na inicialização com uma
mensagem clara, em vez de deixar o erro aparecer como uma exceção confusa da
API mais adiante.

---

## Solução de problemas

| Sintoma                             | Causa provável                              | Correção                                                                |
| ----------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------- |
| `chat not found`                    | O bot nunca recebeu mensagem sua            | Envie `/start` ao bot e reveja o chat ID                                 |
| `401 Unauthorized`                  | Token inválido ou revogado                  | Confira o `TELEGRAM_BOT_TOKEN` no `.env` ou nos Secrets                  |
| `404 NOT_FOUND` no Gemini           | Modelo descontinuado ou nome errado         | Ajuste `GEMINI_MODEL` no `.env` e no workflow                            |
| `503 UNAVAILABLE` no Gemini         | Sobrecarga temporária no servidor do Google | O script já tenta de novo sozinho; se persistir, aguarde alguns minutos  |
| `Bad Request: can't parse entities` | Tag HTML não suportada                      | Verifique se o `html.escape()` foi removido                              |
| `0 notícias encontradas`            | Buscas restritivas ou tudo já enviado       | Adicione termos à lista `buscas` ou rode com `--resetar-cache`           |
| Notícias repetidas no Actions       | Passo `actions/cache` ausente no workflow   | Adicione o passo que restaura/salva a pasta `.cache`                     |
| `O perfil 'x' não existe`           | `PERFIL_ATIVO` com valor inválido           | Use um dos perfis listados na mensagem de erro                           |
| Workflow parou de rodar sozinho     | 60 dias sem atividade no repositório        | Reative na aba Actions ou faça qualquer commit                           |
| `getUpdates` retorna vazio          | Nenhuma mensagem registrada                 | Mande algo ao bot e recarregue                                           |
| Grupo não aparece no `getUpdates`   | Modo privacidade ativo                      | `/setprivacy` → **Disable** no BotFather                                 |
| Variáveis não carregam              | `.env` fora da pasta do script              | Use **Iniciar em** no agendador                                          |

---

## Stack

`feedparser` · `requests` · `google-genai` · `python-dotenv` · Telegram Bot API · GitHub Actions

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
