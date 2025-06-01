```python
import os
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify, Response, abort
from openai import OpenAI
from datetime import datetime

# Importa o utilitário Twilio centralizado
from utils.twilio_utils import send_whatsapp_message
# ATUALIZADO: Importe as novas funções do fluxo de vendas
from utils.fluxo_vendas import listar_categorias, listar_produtos_categoria, adicionar_ao_carrinho, ver_carrinho, finalizar_compra 
# IMPORTANTE: A função get_db_connection E salvar_conversa DEVEM SER IMPORTADAS de um módulo centralizado
from utils.db_utils import get_db_connection, salvar_conversa 

# Blueprints (permanecem inalterados)
from routes.upload_csv import upload_csv_bp
from routes.edit_produtos import edit_produtos_bp
from routes.ver_produtos import ver_produtos_bp
from routes.ver_conversas import ver_conversas_bp 
from routes.gerenciar_vendas import gerenciar_vendas_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_upload")

# Registre os blueprints (permanecem inalterados)
app.register_blueprint(upload_csv_bp, url_prefix="/upload")
app.register_blueprint(edit_produtos_bp, url_prefix="/edit_produtos")
app.register_blueprint(ver_produtos_bp, url_prefix="/ver_produtos")
app.register_blueprint(ver_conversas_bp, url_prefix="/ver_conversas") 
app.register_blueprint(gerenciar_vendas_bp, url_prefix='/gerenciar_vendas')

# Variáveis de ambiente (permanecem inalterados)
openai_api_key = os.environ.get("OPENAI_API_KEY")
RENDER_BASE_URL = "https://teste-bot-9ppl.onrender.com"  # Seu domínio público do Render
client_openai = OpenAI(api_key=openai_api_key)

# Funções de DB e OpenAI (permanecem inalterados, exceto pequena alteração no prompt do GPT)
def carregar_produtos_db():
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM produtos", conn)
        df.columns = [col.strip().lower() for col in df.columns]
        df.fillna("", inplace=True)
        df["nome"] = df["nome"].astype(str).str.lower()
        conn.close()
        return df
    except Exception as e:
        print(f"Erro ao carregar produtos do banco: {e}")
        return pd.DataFrame(columns=["nome", "descricao", "preco", "categoria"])

# ALTERADO: Adicionado filtro de tamanho para evitar buscas por palavras muito curtas
def buscar_produto_no_db(mensagem):
    if len(mensagem.strip()) < 3: # Não busca por palavras muito curtas
        return None
    df = carregar_produtos_db()
    mensagem_lower = mensagem.lower()
    # Usando regex para buscar a palavra completa no nome do produto
    resultados = df[df["nome"].str.contains(r'\b' + mensagem_lower + r'\b', regex=True)] # Busca por palavra completa
    if not resultados.empty:
        respostas = []
        for _, row in resultados.iterrows():
            resposta = f"{row['nome'].capitalize()} - R$ {row['preco']:.2f}\n{row['descricao']}"
            respostas.append(resposta)
        return "\n\n".join(respostas)
    return None

def gerar_contexto_do_db():
    df = carregar_produtos_db()
    contextos = []
    for _, row in df.iterrows():
        contexto = f"{row['nome'].capitalize()} - R$ {row['preco']:.2f} - {row['descricao']}"
        contextos.append(contexto)
    return "\n".join(contextos)

# ALTERADO: Adicionado filtro de tamanho para evitar buscas por palavras muito curtas
def buscar_produto_detalhado(mensagem):
    if len(mensagem.strip()) < 3: # Não busca por palavras muito curtas
        return None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Busca por nome do produto que contenha a mensagem do usuário (case insensitive)
        # Pode ser necessário ajustar a busca aqui para ser mais precisa ou usar um parser
        cur.execute(
            "SELECT id, nome, preco, descricao, categoria, imagem FROM produtos WHERE LOWER(nome) LIKE %s LIMIT 1",
            (f"%{mensagem.lower()}%",)
        )
        produto = cur.fetchone()
        cur.close()
        conn.close()
        if produto:
            return {
                "id": produto[0],
                "nome": produto[1],
                "preco": produto[2],
                "descricao": produto[3],
                "categoria": produto[4],
                "tem_imagem": produto[5] is not None
            }
    except Exception as e:
        print(f"Erro buscar produto detalhado: {e}")
        return None 

def get_gpt_response(mensagem):
    contexto_produtos = gerar_contexto_do_db()
    prompt = f"""
Você é um assistente virtual de vendas da loja Semente Viva, especializada em produtos naturais.
Seu objetivo é oferecer um atendimento humanizado, simpático e eficiente, guiando o cliente durante toda a jornada de compra.
Funil de Vendas:
- Identifique o estágio do cliente: descoberta, consideração, decisão, pós-venda.
- No início da conversa, descubra as necessidades ou objetivos do cliente com perguntas abertas.
- Apresente produtos relevantes conforme o estágio (ex: para novos clientes, foque em apresentação de categorias e benefícios; para clientes recorrentes, apresente promoções e complementos).
- Sempre convide o cliente a avançar para o próximo passo do funil: olhar produtos, tirar dúvidas, montar o carrinho, fechar a compra.
Carrinho de Compras:
- Ajude o cliente a adicionar, remover e revisar produtos no carrinho.
- Informe sempre que um produto foi adicionado ou removido.
- Permita que ele consulte o carrinho a qualquer momento ("Deseja ver o que já escolheu?").
- Mostre um resumo do carrinho antes do fechamento do pedido (produtos, quantidades, valores).
Fotos dos Produtos:
- Descreva os produtos em detalhes. Atualmente, não estamos enviando imagens via WhatsApp, mas essa funcionalidade pode ser ativada no futuro. Para ver as imagens, o cliente pode visitar nosso site ou catálogo.
Diretrizes do atendimento aprimoradas:
1. Sempre utilize linguagem personalizada, cordial e animada.
2. Proponha próximos passos claros conforme o estágio de compra do cliente.
3. Use, sempre que possível, histórico da conversa e preferências para personalizar sugestões.
4. Mantenha respostas diretas, com informações objetivas e relevantes.
5. Demonstre empatia e ofereça ajuda ativa.
6. Nunca solicite dados sensíveis.
7. Encaminhe para atendimento humano caso necessário.
8. Finalize cada atendimento agradecendo e se colocando à disposição para dúvidas ou acompanhamentos futuros.

**Instruções Cruciais para o Chabot:**
- Sempre que responder a uma pergunta ou sugestão, **guie o cliente explicitamente** sobre o que ele pode fazer em seguida. Ex: "Para ver todos os nossos produtos, digite 'produtos'.", "Para adicionar algo ao carrinho, use 'add <ID> <quantidade>'.", "Para ver seu carrinho, digite 'carrinho'."
- Se o cliente perguntar sobre um produto específico, forneça a descrição e o preço, e **sugira que ele digite 'add <ID do produto> <quantidade>'** para adicionar ao carrinho ou 'produtos' para ver o catálogo.
- Se o cliente expressar interesse em comprar algo, **lembre-o de usar o comando 'add' com ID e quantidade.**
- Sempre ofereça ajuda com "Posso ajudar em algo mais?" ou "Como posso prosseguir com sua jornada de compra?"


Catálogo de produtos (com fotos - para sua referência, mas descreva):
{contexto_produtos}
Mensagem do cliente: {mensagem}
"""
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Responda sempre em português com educação e clareza."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# =========================
# Webhook WhatsApp - Lógica do carrinho integrada aqui
# =========================

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender_number = request.form.get("From", "").replace("whatsapp:", "")
    user_message = request.form.get("Body", "").strip()
    user_message_lower = user_message.lower()

    if not sender_number or not user_message:
        return "Dados insuficientes", 400

    resposta_final = "" # Inicializa a resposta final

    # 1. Prioridade: Saudações e Menu Principal
    if user_message_lower in ["oi", "olá", "ola", "oi tudo bem", "menu", "começar", "iniciar"]: # Mais saudações
        resposta_final = "Olá! Seja muito bem-vindo(a) à Semente Viva! 🌱 Sou seu assistente virtual para ajudar você a encontrar os melhores produtos naturais. " \
                         "Estou aqui para tornar sua jornada de compra fácil e agradável.\n\n" \
                         "Para começarmos, veja as opções disponíveis:\n" \
                         "👉 Digite `produtos` para ver nosso catálogo completo.\n" \
                         "👉 Digite `carrinho` para conferir os itens que você já escolheu.\n" \
                         "👉 Digite `finalizar` para concluir seu pedido.\n" \
                         "Você também pode perguntar sobre produtos específicos! Por exemplo: 'Quero saber sobre Whey Protein'."
    
    # 2. Prioridade: Comandos do Carrinho
    elif user_message_lower.startswith('add '):
        parts = user_message_lower.split()
        if len(parts) == 3:
            try:
                prod_id = int(parts[1])
                quantidade = int(parts[2])
                resposta_retorno_fluxo = adicionar_ao_carrinho(sender_number, prod_id, quantidade)
                # Adiciona orientação extra após adicionar ao carrinho
                resposta_final = f"{resposta_retorno_fluxo}\n\n" \
                                 "Perfeito! O que você gostaria de fazer agora?\n" \
                                 "👉 Digite `produtos` para continuar comprando.\n" \
                                 "👉 Digite `carrinho` para ver o que você já tem.\n" \
                                 "👉 Digite `finalizar` para ir para o fechamento do pedido."
            except ValueError:
                resposta_final = "Ops! Formato inválido para adicionar ao carrinho. Por favor, use: `add <ID do produto> <quantidade>`. Ex: `add 1 2`."
        else:
            resposta_final = "Ops! Formato inválido para adicionar ao carrinho. Por favor, use: `add <ID do produto> <quantidade>`. Ex: `add 1 2`."
    
    elif user_message_lower in ["carrinho", "ver carrinho", "meu carrinho"]: # Mais sinônimos para carrinho
        resposta_retorno_fluxo = ver_carrinho(sender_number)
        resposta_final = f"{resposta_retorno_fluxo}\n\n" \
                         "Pronto para dar o próximo passo?\n" \
                         "👉 Digite `finalizar` para confirmar e fechar seu pedido.\n" \
                         "👉 Digite `produtos` para adicionar mais itens."
    
    elif user_message_lower == 'finalizar':
        resposta_retorno_fluxo = finalizar_compra(sender_number)
        resposta_final = f"{resposta_retorno_fluxo}\n\n" \
                         "Agradecemos a sua compra! Se precisar de algo mais ou tiver dúvidas futuras, é só chamar. Digite `menu` a qualquer momento."
    
    # 3. Prioridade: Listagem de Produtos e Categorias
    elif user_message_lower in ["produtos", "ver produtos", "catalogo", "cardapio"]: # Mais sinônimos para produtos
        resposta_retorno_fluxo = listar_categorias() # Ou listar todos os produtos se não tiver categorias
        resposta_final = f"{resposta_retorno_fluxo}\n\n" \
                         "Se quiser ver todos os produtos de uma categoria, é só digitar o nome dela (ex: `chá`).\n" \
                         "Para adicionar, digite `add <ID do produto> <quantidade>`. Qual categoria você gostaria de explorar?"
    
    # Verifica se a mensagem é um nome de categoria existente (ajuste conforme suas categorias)
    elif user_message_lower in ["chá", "chás", "suplementos", "óleos", "veganos", "goiabada"]: # Exemplo de categoria
        resposta_retorno_fluxo = listar_produtos_categoria(user_message_lower)
        resposta_final = f"{resposta_retorno_fluxo}\n\n" \
                         "Gostou de algum produto? Digite `add <ID do produto> <quantidade>` para adicioná-lo ao seu carrinho!\n" \
                         "Ou digite `produtos` para ver outras categorias."

    # 4. Prioridade: Busca por Produto Detalhado (COM ENVIO DE IMAGEM COMENTADO)
    if not resposta_final: 
        produto_detalhado = buscar_produto_detalhado(user_message)

        if produto_detalhado:
            resposta_final = (
                f"Que ótimo! Encontrei o produto que você busca:\n"
                f"*{produto_detalhado['nome'].capitalize()}* - R$ {produto_detalhado['preco']:.2f}\n" 
                f"Detalhes: {produto_detalhado['descricao']}"
            )
            
            # LÓGICA DE ENVIO DE IMAGEM COMENTADA (ative quando sua conta estiver verificada)
            if produto_detalhado["tem_imagem"]:
                img_url = f"{RENDER_BASE_URL}/ver_produtos/imagem/{produto_detalhado['id']}"
                # send_whatsapp_message(to_number=sender_number, body=resposta_final, media_url=img_url)
                # salvar_conversa(sender_number, user_message, resposta_final)
                # return "OK", 200 # Este return deve ser comentado se o send_whatsapp_message acima for comentado
            
            # Adiciona a orientação. Se a imagem for ativada, esta orientação complementa.
            resposta_final += "\n\nPara ver mais detalhes e fotos, por favor, visite nosso catálogo no site (link do site) ou digite 'produtos' para ver outras opções aqui.\n" \
                              f"Se quiser adicionar '{produto_detalhado['nome'].capitalize()}' ao carrinho, use o comando: `add {produto_detalhado['id']} <quantidade>`."
    
    # 5. Prioridade: Busca Geral de Produtos no DB ou GPT
    if not resposta_final: 
        resposta_db = buscar_produto_no_db(user_message)
        if resposta_db:
            resposta_final = f"Encontrei algo parecido com sua busca:\n{resposta_db}\n\n" \
                             "Posso te ajudar a adicionar algum item ao carrinho? Lembre-se de usar `add <ID> <quantidade>`."
        else:
            resposta_final = get_gpt_response(user_message)
            # Após a resposta do GPT, adiciona um guia geral se ela não for muito específica
            if not any(cmd in resposta_final.lower() for cmd in ['produtos', 'carrinho', 'finalizar', 'add ']):
                 resposta_final += "\n\nPara explorar mais, você pode:\n" \
                                   "👉 Digitar `produtos` para ver nosso catálogo.\n" \
                                   "👉 Digitar `carrinho` para gerenciar seus itens.\n" \
                                   "👉 Digitar `finalizar` para concluir seu pedido."


    # --- Envio da Mensagem Final ---
    if resposta_final: 
        send_whatsapp_message(
            to_number=sender_number,
            body=resposta_final
        )
        salvar_conversa(sender_number, user_message, resposta_final)
    else: # Fallback caso nenhuma lógica gere resposta
        send_whatsapp_message(
            to_number=sender_number,
            body="Desculpe, não consegui processar sua solicitação. Por favor, tente novamente digitando 'menu' para ver as opções."
        )
        salvar_conversa(sender_number, user_message, "Erro: Sem resposta gerada.")
    
    return "OK", 200

# Rotas do painel (permanecem inalteradas)
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
