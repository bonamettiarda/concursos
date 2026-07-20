# Monitor de Convocação de Concurso

Vigia o Diário Oficial das cidades onde você presta concurso e te avisa toda vez
que sai uma **convocação / nomeação / posse / homologação**.

- **Custo: R$ 0.** Roda na nuvem grátis do **GitHub Actions**. Seu PC pode estar desligado.
- **Não usa IA / não gasta token de Claude nenhum.** É um scraper Python simples.
- **Três canais de aviso** — use um, dois ou os três ao mesmo tempo:
  📱 Telegram · ✉️ E-mail · 🔔 Push no celular (iPhone/Android via ntfy.sh)
- Já vem pronto pra: **Catanduvas-PR**, **Cambé-PR** (adaptador próprio, site
  direto), **Goioerê-PR**, **Prado Ferreira-PR**, **Marechal C. Rondon-PR**
  (via Querido Diário) e o concurso estadual **SESA/SEAP-PR** (Edital
  265/2025, cadastro de reserva). Adicionar outra cidade → ver
  [`ADICIONAR-CIDADE.md`](ADICIONAR-CIDADE.md).

> ⚠️ **Goioerê, Prado Ferreira e Marechal C. Rondon** usam a API pública do
> [Querido Diário](https://queridodiario.ok.org.br/) (Open Knowledge Brasil)
> em vez de raspar o site de cada prefeitura direto — várias delas bloqueiam
> robôs ou (no caso de Prado Ferreira) usam um portal estadual (AMP/SIGPub)
> cuja busca por palavra-chave exige resolver um **captcha do Google**, o
> que não dá pra automatizar de forma confiável nem é algo que eu tente
> contornar. A cobertura do Querido Diário varia por cidade; **rode o
> Passo 2 (teste manual) e confira o log** antes de confiar 100% — se
> alguma cidade nunca aparecer nada, me avisa que eu procuro outra fonte.

> **Como funciona a escolha de canal:** o script envia por **todos os canais que
> você configurar**. Configurou só o e-mail? Vai só e-mail. Configurou os três?
> Vão os três. Não precisa mexer no código pra escolher — é só preencher (ou não)
> os *Secrets* de cada canal no passo 3.

---

## Passo 1 — Subir pro GitHub (uma vez)

1. Crie uma conta no GitHub (grátis) se ainda não tiver.
2. Crie um repositório **novo** (pode ser **privado**) e suba **todos** estes arquivos.
3. Na aba **Actions** do repositório, clique pra **habilitar os workflows** (o GitHub
   pede uma confirmação na 1ª vez).

## Passo 2 — Ligar e testar

1. Aba **Actions** → workflow **monitor-concurso** → botão **Run workflow**.
2. Veja o log: na 1ª vez ele "aprende" tudo que já existe (não te enche de aviso
   retroativo). Da 2ª rodada em diante, só avisa do que for **novo**.
3. Depois disso ele roda **sozinho** de seg a sex (horários no arquivo
   `.github/workflows/monitor.yml` — dá pra mudar lá).

## Seus dados (pra copiar e colar no Passo 3)

| Canal      | Secret            | Valor que você vai usar                                    |
|------------|--------------------|-------------------------------------------------------------|
| Telegram   | `TELEGRAM_CHAT_ID` | pegue no celular **(43) 99628-0007** seguindo o passo a passo abaixo |
| E-mail     | `EMAIL_DESTINO`    | `bonamettiarda@gmail.com`                                    |

> O Telegram **não usa o número de telefone diretamente** no script — ele usa
> um "chat id" numérico que você obtém conversando com seu próprio bot pelo
> Telegram instalado nesse mesmo número. Passo a passo completo na Opção A
> abaixo.

## Passo 3 — Escolher como quer ser avisado

Os avisos são configurados em **Settings → Secrets and variables → Actions →
New repository secret**. Crie só os secrets do(s) canal(is) que você quiser.
**Nada de senha vai no código** — tudo fica nos Secrets do GitHub.

---

### 📱 Opção A — Telegram

**Você precisa de:** um bot (grátis, 2 min) e o seu "chat id".

1. No Telegram, fale com **@BotFather** → mande `/newbot` → escolha um nome. Ele
   devolve um **token** tipo `123456:ABC-DEF...`. **Copie.**
2. Mande qualquer mensagem (ex.: "oi") pro seu bot recém-criado.
3. Abra no navegador: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   (troque `<SEU_TOKEN>`). Procure `"chat":{"id":123456789}` — esse número é o seu chat id.

**Secrets a criar no GitHub:**

| Nome do Secret       | O que colar                          |
|----------------------|--------------------------------------|
| `TELEGRAM_TOKEN`     | o token do BotFather                 |
| `TELEGRAM_CHAT_ID`   | o número do chat id                  |

---

### ✉️ Opção B — E-mail (Gmail)

**Você precisa de:** um Gmail com **verificação em duas etapas** ligada e uma
**"senha de app"** (o Gmail não deixa usar a senha normal em script).

1. Ative a verificação em 2 etapas da conta Google.
2. Gere uma **senha de app**: conta Google → Segurança → "Senhas de app" →
   crie uma (ele te dá 16 letras). **Copie.**

**Secrets a criar no GitHub:**

| Nome do Secret     | O que colar                                             |
|--------------------|---------------------------------------------------------|
| `EMAIL_REMETENTE`  | seu Gmail que envia, ex.: `seuemail@gmail.com`          |
| `EMAIL_SENHA_APP`  | a senha de app de 16 letras (sem espaços)               |
| `EMAIL_DESTINO`    | pra onde mandar o aviso (pode ser o mesmo e-mail)       |

> Usa outro provedor (Outlook etc.)? Crie também os secrets opcionais
> `EMAIL_SMTP_HOST` e `EMAIL_SMTP_PORT`. Padrão = Gmail (`smtp.gmail.com` / `587`).

---

### 🔔 Opção C — Push no celular (recomendado pra iPhone) via ntfy.sh

**Zero cadastro, zero custo.** É o mais simples pra iPhone 16 Pro Max.

1. Baixe o app **ntfy** na App Store (ícone de sininho, de graça).
2. No app, toque em **+** e **inscreva-se num tópico**. O tópico é um nome que
   **só você escolhe e deve ser difícil de adivinhar** (funciona como senha).
   Ex.: `concurso-med-9f3k2x` (invente o seu, único e secreto).

**Secret a criar no GitHub:**

| Nome do Secret | O que colar                                        |
|----------------|----------------------------------------------------|
| `NTFY_TOPIC`   | exatamente o mesmo nome de tópico que você assinou |

> Como o tópico é público pra quem souber o nome, **escolha um nome longo e
> aleatório** e não compartilhe. (Dá pra usar um servidor ntfy privado depois,
> mas pro seu caso o padrão grátis já resolve.)

---

## Rodar no seu PC (opcional, pra testar antes)

```bash
pip install -r requirements.txt
python monitor.py
```

Sem os secrets configurados, ele só imprime na tela — ótimo pra ver se está
achando as publicações certas antes de ligar os avisos.

Pra testar um canal específico no PC, defina as variáveis de ambiente antes de
rodar. Ex. (Windows PowerShell):

```powershell
$env:NTFY_TOPIC="concurso-med-9f3k2x"
python monitor.py
```

---

## O que muda / o que você adapta

| Quero mudar...                         | Onde mexer                                             |
|----------------------------------------|-------------------------------------------------------|
| As cidades que acompanho               | Lista `CIDADES` no `monitor.py` (ver ADICIONAR-CIDADE.md) |
| As palavras que disparam o aviso       | Lista `PALAVRAS_ALVO` no topo do `monitor.py`         |
| A frequência das checagens             | O `cron:` em `.github/workflows/monitor.yml`          |
| Por onde recebo o aviso                | Quais Secrets eu crio no GitHub (passo 3)             |
