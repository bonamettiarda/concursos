# Como adicionar outra cidade

**A verdade sem enrolação:** cada prefeitura tem um site de Diário Oficial
diferente. Não existe um botão mágico que cubra todas — cada cidade precisa de um
"adaptador" (um pedacinho de código que sabe ler *aquele* site). A boa notícia:
o molde já está pronto e, pra muitos casos, é rápido.

Existem **4 cenários**. Descubra em qual a sua cidade cai — comece pelo Cenário 0,
é o mais rápido de tentar primeiro pra cidades pequenas/médias.

---

## Cenário 0 — Tentar primeiro: API do Querido Diário

O [Querido Diário](https://queridodiario.ok.org.br/) (Open Knowledge Brasil) já
indexa o Diário Oficial de milhares de municípios brasileiros, então às vezes
você nem precisa descobrir a plataforma da prefeitura.

**O que fazer:**
1. Descubra o **código IBGE** da cidade (7 dígitos) — busque "código IBGE + nome
   da cidade" no Google.
2. Registre na lista `CIDADES`:

```python
CIDADES = [
    criar_adaptador_querido_diario("Nome Cidade-UF", "CODIGO_IBGE_AQUI"),
]
```

3. Rode `python monitor.py` e veja se aparece alguma coisa. **Cobertura não é
   garantida** — se a cidade nunca indexou nada no Querido Diário, essa opção
   não funciona e você cai pro Cenário 1, 2 ou 3.

---

## Cenário 1 — Cidade usa a MESMA plataforma da Catanduvas (o mais fácil)

**Como saber:** abra o Diário Oficial da cidade e olhe a URL da busca. Se ela for
parecida com `.../filtrarDiarioSearch` e o link de cada publicação for
`.../diario_view?id=NUMERO`, é a mesma plataforma.

**O que fazer:** no `monitor.py`, na lista `CIDADES`, adicione **uma linha** só
trocando o nome e o domínio:

```python
CIDADES = [
    adaptador_portal_padrao("Catanduvas-PR", "https://catanduvas.pr.gov.br"),
    adaptador_portal_padrao("Nome Cidade-PR", "https://SITE-DA-CIDADE.pr.gov.br"),  # <- PREENCHER
]
```

Pronto. Testa com `python monitor.py` e vê se aparecem publicações daquela cidade.

---

## Cenário 2 — Cidade usa OUTRA plataforma, mas é uma tabela HTML normal

Muitos diários são uma tabela simples (data | título | link), só que com nomes de
URL e colunas diferentes. Aí você escreve um adaptador próprio. Use este molde —
copie pro `monitor.py` (perto do `adaptador_portal_padrao`) e preencha os
`# PREENCHER`:

```python
def adaptador_minhacidade():
    NOME = "Minha Cidade-UF"                              # PREENCHER
    URL  = "https://diario.minhacidade.uf.gov.br/busca"  # PREENCHER: a URL da busca
    # PREENCHER: os parâmetros que o site aceita na URL (veja na barra do navegador
    # depois de fazer uma busca por "concurso"). Ex.: {"q": "concurso", "ano": "2026"}
    params = {"q": "concurso"}

    r = requests.get(URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    sopa = BeautifulSoup(r.text, "html.parser")

    resultados = []
    tabela = sopa.find("table")            # PREENCHER se não for <table>: ex. sopa.select(".lista-publicacao")
    if not tabela:
        return resultados

    for linha in tabela.find_all("tr")[1:]:
        celulas = linha.find_all("td")
        if len(celulas) < 2:
            continue
        # PREENCHER: qual coluna é a data, qual é o título, onde está o link.
        data     = celulas[0].get_text(strip=True)
        titulo   = celulas[1].get_text(strip=True)
        a        = linha.find("a")
        link     = a["href"] if a and a.has_attr("href") else None
        if link and link.startswith("/"):
            link = "https://diario.minhacidade.uf.gov.br" + link   # PREENCHER o domínio

        if not bate_palavra(titulo):       # reaproveita seu filtro de palavras-chave
            continue

        resultados.append({
            "cidade": NOME, "data": data, "titulo": titulo,
            "categoria": "", "link": link,
        })
    return resultados
```

Depois registre na lista `CIDADES`:

```python
CIDADES = [
    adaptador_portal_padrao("Catanduvas-PR", "https://catanduvas.pr.gov.br"),
    adaptador_minhacidade,                 # <- só o nome da função, sem parênteses
]
```

### Como descobrir os seletores certos
1. Abra o Diário no navegador e faça uma busca por `concurso`.
2. Aperte **F12** (ferramentas do desenvolvedor) → aba **Elements**.
3. Clique com o botão direito numa linha de resultado → **Inspect**. Veja se é
   `<table>`/`<tr>`/`<td>` ou uma lista `<ul>/<li>` ou `<div>`s — e ajuste o molde.
4. Olhe a URL depois da busca: os parâmetros (`?q=...&ano=...`) vão pro `params`.

---

## Cenário 3 — O site bloqueia robô ou depende de JavaScript

Sinais: a página vem "vazia" no script, ou aparece "navegador incompatível", ou os
resultados só surgem depois que a página "carrega sozinha" no navegador.
(Foi o caso do portal da UNIOESTE nos nossos testes.)

Aí `requests` sozinho não resolve — precisaria de um navegador de verdade
(Selenium/Playwright), que é mais pesado e nem sempre roda de graça fácil.

**Antes de partir pra isso, procure uma fonte alternativa** — quase sempre existe:
- O **próprio site da prefeitura** costuma ter um Diário Oficial próprio (foi o que
  usamos na Catanduvas), mais fácil que o portal da banca.
- Muitas cidades publicam no **Diário Oficial dos Municípios** do estado (ex.: no PR,
  plataformas tipo AMP/DIOEMS). Uma URL dessas costuma ser tabela simples (cenário 2).

Se você me mandar a URL do diário da cidade, eu monto o adaptador pra você.

---

## Testando qualquer cidade nova

```bash
python monitor.py
```

- Apareceram as publicações da cidade nova no print? ✅ funcionou.
- Não apareceu nada? Confira: a URL/params estão certos? O filtro de palavras
  (`PALAVRAS_ALVO`) bate com o texto do título daquele site?
- Deu erro de conexão/bloqueio? Provável cenário 3 — procure a fonte alternativa.
