# Bot de Notícias com Curadoria por IA

Motor de monitoramento em Python que coleta notícias de uma fonte configurável,
usa a API do Gemini para selecionar as mais relevantes segundo um critério que
você define, e entrega o resumo no Telegram.

Nasceu como um bot de notícias condominiais, mas a fonte, o critério de
julgamento e o formato de saída são todos parametrizáveis — o mesmo motor
serve para monitorar tarifas de energia, movimentos de concorrentes, editais
de licitação ou qualquer outro recorte de informação.

```
┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌──────────┐
│  FONTE   │ -> │  CURADORIA  │ -> │ MONTAGEM │ -> │  ENTREGA │
│ RSS/HTML │    │   (Gemini)  │    │ (Python) │    │(Telegram)│
└──────────┘    └─────────────┘    └──────────┘    └──────────┘
  trocável        critério          links do          canal
                  definido          feed puro       trocável
```

---

## Índice

- [Instalação](#instalação)
- [Configurar o Telegram (passo a passo)](#configurar-o-telegram-passo-a-passo)
- [Configurar a API do Gemini](#configurar-a-api-do-gemini)
- [Primeira execução](#primeira-execução)
- [Adaptando para outras finalidades](#adaptando-para-outras-finalidades)
- [Dominando a busca do Google News](#dominando-a-busca-do-google-news)
- [Trocando a fonte: outros feeds e scraping](#trocando-a-fonte-outros-feeds-e-scraping)
- [Agendamento](#agendamento)
- [Decisões técnicas](#decisões-técnicas)
- [Solução de problemas](#solução-de-problemas)

---

## Instalação

Requer Python 3.9 ou superior.

```bash
git clone https://github.com/MiguelACJR87/bot-noticias-condominiais.git
cd bot-noticias-condominiais
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

| Comando | O que faz |
|---|---|
| `/setdescription` | Texto exibido antes de alguém iniciar a conversa |
| `/setabouttext` | Descrição curta no perfil do bot |
| `/setuserpic` | Define a foto de perfil |
| `/setcommands` | Cadastra o menu de comandos |

---

## Configurar a API do Gemini

**1.** Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
e faça login com sua conta Google.

**2.** Clique em **Create API key** e selecione um projeto (ou deixe criar um
novo automaticamente).

**3.** Copie a chave gerada. Ela aparece uma única vez de forma completa.

O plano gratuito do AI Studio tem cota diária suficiente para uma execução por
dia com folga — este bot faz **uma única chamada** por execução.

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

```env
GEMINI_API_KEY=AIzaSyD...
TELEGRAM_BOT_TOKEN=7891234567:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
TELEGRAM_CHAT_ID=936478817
GEMINI_MODEL=
PERFIL_ATIVO=
```

Os dois últimos podem ficar vazios — o script usa os padrões.

Rode:

```bash
python automacao_sindico.py
```

Saída esperada:

```
1. Buscando notícias recentes [perfil: condominios]...
-> 17 notícias encontradas.
2. Analisando as notícias com o Gemini (gemini-3.6-flash)...
-> 6 notícias selecionadas.
3. Montando a mensagem e resolvendo os links...
4. Enviando o resumo final para o Telegram...
-> Mensagem entregue com sucesso no seu celular!
```

> O arquivo `.env` está no `.gitignore` e não vai para o repositório.

---

## Adaptando para outras finalidades

Aqui está o coração do projeto. O comportamento inteiro é definido por um
**perfil** — um bloco de quatro campos no topo do script.

```python
PERFIS = {
    "condominios": {
        "titulo": "🏢 <b>As Notícias Condominiais do Dia</b> 🏢",
        "busca": "condominio OR sindico when:1d",
        "persona": "Você é um especialista do mercado imobiliário e gestão condominial.",
        "criterio": "mais impactantes, urgentes ou relevantes para síndicos e moradores",
    },
}
```

| Campo | Função |
|---|---|
| `titulo` | Cabeçalho da mensagem no Telegram. Aceita as tags `<b>` e `<i>` |
| `busca` | Consulta enviada ao Google News. Define **o que entra** no funil |
| `persona` | Quem o modelo "é" ao julgar. Define a lente da análise |
| `criterio` | O que torna uma notícia relevante. Define **o que sai** do funil |

Trocar de finalidade é trocar uma linha no `.env`:

```env
PERFIL_ATIVO=tecnologia
```

### Perfis já incluídos

| Perfil | Monitora |
|---|---|
| `condominios` | Gestão condominial, síndicos, legislação do setor |
| `energia` | Tarifas, ANEEL, bandeiras tarifárias |
| `saneamento` | Água, saneamento, concessionárias regionais |
| `tecnologia` | IA e desenvolvimento de software |
| `local` | Notícias de uma cidade ou estado |
| `concorrencia` | Menções a empresas específicas |

### Criando o seu

Copie qualquer bloco e ajuste os quatro campos. Exemplo para monitorar
oportunidades públicas:

```python
"licitacoes": {
    "titulo": "📋 <b>Radar de Licitações</b> 📋",
    "busca": "licitacao OR pregao eletronico OR edital when:2d",
    "persona": "Você é um analista comercial especializado em vendas para o setor público.",
    "criterio": "que representam oportunidades reais de negócio para prestadores de serviço",
},
```

Ou para acompanhar um tema regulatório:

```python
"regulatorio": {
    "titulo": "⚖️ <b>Alertas Regulatórios</b> ⚖️",
    "busca": "LGPD OR ANPD OR protecao de dados when:3d",
    "persona": "Você é um advogado especializado em proteção de dados.",
    "criterio": "que exigem alguma adequação prática por parte das empresas",
},
```

**A `persona` importa mais do que parece.** A mesma notícia sobre reajuste
tarifário é lida de forma diferente por um "analista financeiro" e por um
"defensor do consumidor". Trocar essa frase muda quais notícias sobem no
ranking e como o motivo é escrito.

### Ajustes de volume e ritmo

```python
QUANTIDADE_FINAL = 6          # quantas notícias entram no resumo
MAX_NOTICIAS_ANALISADAS = 30  # quantas manchetes o modelo avalia
```

Aumentar `MAX_NOTICIAS_ANALISADAS` dá mais material para o modelo escolher, ao
custo de um prompt maior. Para nichos com pouco volume, combine com uma janela
de tempo mais larga (`when:7d`) em vez de aumentar esse número.

### Mudando o formato da saída

O JSON pedido ao modelo define a estrutura. Para incluir uma classificação de
urgência, por exemplo, adicione o campo em `montar_prompt()`:

```
  "urgencia" - "alta", "media" ou "baixa"
```

E use em `montar_mensagem()`:

```python
selo = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}
bloco = f"{selo.get(noticia['urgencia'], '')} {noticia['emoji']} <b>{titulo}</b>"
```

Lembre de propagar o campo novo no loop de `selecionar_com_ia()`.

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

## Dominando a busca do Google News

O campo `busca` aceita operadores que refinam bastante o resultado.

| Operador | Efeito | Exemplo |
|---|---|---|
| `OR` | Qualquer um dos termos | `condominio OR sindico` |
| `"aspas"` | Expressão exata | `"convenção de condomínio"` |
| `-` | Exclui o termo | `energia -futebol` |
| `when:` | Janela de tempo | `when:1h`, `when:1d`, `when:7d` |
| `site:` | Restringe a um domínio | `site:g1.globo.com` |
| `intitle:` | Só no título da matéria | `intitle:tarifa` |
| `allintext:` | Todos os termos no corpo | `allintext:sindico multa` |

Combinando:

```python
"busca": '"gestão condominial" OR intitle:sindico -futebol when:2d'
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
montagem de `URL_RSS`:

```python
# Por tópico: BUSINESS, TECHNOLOGY, SCIENCE, HEALTH, SPORTS, ENTERTAINMENT
URL_RSS = (
    f"https://news.google.com/rss/headlines/section/topic/TECHNOLOGY"
    f"?hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
)

# Por localidade
URL_RSS = (
    f"https://news.google.com/rss/headlines/section/geo/Recife"
    f"?hl={IDIOMA}&gl={REGIAO}&ceid={EDICAO}"
)
```

---

## Trocando a fonte: outros feeds e scraping

O Google News é o padrão por conveniência, mas a arquitetura não depende dele.
Qualquer função que devolva uma lista de dicionários com `titulo`, `link` e
`fonte` pode substituir a `buscar_noticias_condominiais()`.

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
    URL_RSS,  # o Google News continua na jogada
]

def buscar_noticias_condominiais():
    print(f"1. Buscando notícias recentes [perfil: {PERFIL_ATIVO}]...")
    noticias = []
    vistos = set()

    for url in FEEDS:
        feed = feedparser.parse(url)
        origem = feed.feed.get("title", "")

        for entrada in feed.entries[:15]:
            if entrada.link in vistos:
                continue
            vistos.add(entrada.link)
            noticias.append({
                "titulo": entrada.title,
                "link": entrada.link,
                "fonte": origem,
            })

    print(f"-> {len(noticias)} notícias encontradas.")
    return noticias[:MAX_NOTICIAS_ANALISADAS]
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

```python
import time

for url in urls:
    coletar(url)
    time.sleep(2)
```

**Identifique-se.** Um User-Agent honesto com forma de contato é cortesia e
evita bloqueios:

```python
USER_AGENT = "RadarCondominial/1.0 (+https://github.com/seu-usuario/seu-repo)"
```

**Cacheie durante o desenvolvimento.** Enquanto você ajusta os seletores,
salve o HTML em disco e trabalhe sobre o arquivo. Não faça vinte requisições
ao servidor alheio para testar uma expressão regular.

**Falhe com elegância.** Sites mudam. Envolva a coleta em `try/except` e trate
lista vazia como situação normal, não como erro fatal.

---

## Agendamento

### Windows — Agendador de Tarefas

**1.** Abra o menu Iniciar e busque por **Agendador de Tarefas**.

**2.** No painel direito, clique em **Criar Tarefa Básica**.

**3.** Nome: `Bot Notícias`. Avance.

**4.** Disparador: **Diariamente**. Defina o horário (ex.: 07:00).

**5.** Ação: **Iniciar um programa**.

**6.** Preencha:

| Campo | Valor |
|---|---|
| Programa | `C:\Users\SEU_USUARIO\anaconda3\python.exe` |
| Argumentos | `automacao_sindico.py` |
| Iniciar em | `C:\Users\SEU_USUARIO\Desktop\Projetos\bot_noticias` |

O campo **Iniciar em** é obrigatório — sem ele o script não encontra o `.env`.

Para descobrir o caminho do seu Python:

```powershell
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

### GitHub Actions

Roda na nuvem, sem depender da sua máquina. Crie
`.github/workflows/diario.yml`:

```yaml
name: Resumo diário

on:
  schedule:
    - cron: "0 10 * * *"  # 10h UTC = 7h em Brasília
  workflow_dispatch:

jobs:
  executar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python automacao_sindico.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          PERFIL_ATIVO: condominios
```

As credenciais vão em **Settings → Secrets and variables → Actions → New
repository secret**. Nunca no arquivo YAML.

Um bônus dessa abordagem: para rodar vários perfis, basta duplicar o step com
um `PERFIL_ATIVO` diferente.

---

## Decisões técnicas

Notas de estudo sobre os problemas encontrados durante o desenvolvimento e o
raciocínio por trás de cada solução.

### Os links não passam pelo modelo

**Problema.** Na primeira versão, o prompt enviava título + link ao Gemini e
pedia a mensagem já formatada de volta. Os links chegavam quebrados no
Telegram.

**Causa.** As URLs do RSS do Google News são strings base64 de 200+ caracteres.
Um LLM não copia isso de forma confiável — ele trunca, altera um caractere ou
completa o padrão de memória. O resultado parece uma URL válida, mas não é.

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
quando a família 1.5 foi descontinuada. O tratamento de erro agora detecta o
404 e lista os modelos disponíveis para a chave, transformando uma falha opaca
em diagnóstico. O modelo também é configurável por variável de ambiente, sem
alterar o código.

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

### Credenciais fora do código

Chave de API e token de bot ficam em `.env`, carregado por `python-dotenv` e
ignorado pelo Git. O `.env.example` documenta quais variáveis existem sem
revelar valores. A função `validar_config()` falha logo na inicialização com
uma mensagem clara, em vez de deixar o erro aparecer como uma exceção confusa
da API mais adiante.

---

## Solução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| `chat not found` | O bot nunca recebeu mensagem sua | Envie `/start` ao bot e reveja o chat ID |
| `401 Unauthorized` | Token inválido ou revogado | Confira o `TELEGRAM_BOT_TOKEN` no `.env` |
| `404 NOT_FOUND` no Gemini | Modelo descontinuado | O script lista os disponíveis; escolha um |
| `503 UNAVAILABLE` no Gemini | Sobrecarga temporária no servidor do Google | O script já tenta de novo sozinho; se persistir, aguarde alguns minutos |
| `Bad Request: can't parse entities` | Tag HTML não suportada | Verifique se o `html.escape()` foi removido |
| `0 notícias encontradas` | Busca restritiva demais | Amplie a janela (`when:7d`) ou os termos |
| `getUpdates` retorna vazio | Nenhuma mensagem registrada | Mande algo ao bot e recarregue |
| Grupo não aparece no `getUpdates` | Modo privacidade ativo | `/setprivacy` → **Disable** no BotFather |
| Variáveis não carregam | `.env` fora da pasta do script | Use **Iniciar em** no agendador |

---

## Stack

`feedparser` · `requests` · `google-genai` · `python-dotenv` · Telegram Bot API

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
