# Teste-bot-main/utils/view_handlers.py

from .db_utils import get_bot_config
from .fluxo_vendas import listar_categorias, listar_produtos_categoria
from .twilio_utils import send_reply_buttons, send_list_picker, send_text

def send_initial_view(conta_id, to_number, from_number):
    """Envia a tela inicial com o menu principal."""
    bot_config = get_bot_config(conta_id)
    
    greeting = bot_config.get('saudacao_personalizada', 'Olá! Bem-vindo(a). Como posso ajudar?')
    
    buttons = [
        {'id': 'view_categories', 'title': '🛍️ Ver Produtos'},
        {'id': 'talk_to_human', 'title': '💬 Falar com Atendente'},
        {'id': 'view_faq', 'title': 'ℹ️ Dúvidas Frequentes'}
    ]
    
    send_reply_buttons(to_number, from_number, greeting, buttons, conta_id)

def send_categories_view(conta_id, to_number, from_number):
    """Envia a tela com a lista de categorias de produtos."""
    categorias = listar_categorias(conta_id)
    
    if not categorias:
        send_text(to_number, from_number, "Ainda não temos produtos cadastrados em nosso catálogo.", conta_id)
        return

    rows = []
    for cat in categorias:
        rows.append({'id': f'category_{cat}', 'title': cat})
        
    sections = [{'title': 'Nossas Categorias', 'rows': rows}]
    
    send_list_picker(
        to_number=to_number,
        from_number=from_number,
        body="Excelente! Toque na categoria que deseja explorar.",
        button_text="Categorias",
        sections=sections,
        conta_id=conta_id
    )

def send_products_from_category_view(conta_id, to_number, from_number, category_name):
    """Envia os produtos de uma categoria específica."""
    produtos = listar_produtos_categoria(conta_id, category_name)

    if not produtos:
        send_text(to_number, from_number, f"Não encontrei produtos na categoria '{category_name}'.", conta_id)
        return

    # Informa o cliente sobre o que ele vai ver
    send_text(to_number, from_number, f"Certo, aqui estão os produtos de *{category_name}*:", conta_id)

    # Envia uma mensagem para cada produto
    for produto in produtos:
        # Futuramente, aqui podemos adicionar uma imagem com `send_media_message`
        product_text = f"*{produto['nome']}*\n"
        product_text += f"_{produto.get('descricao', 'Sem descrição.')}_\n\n"
        product_text += f"Preço: R$ {float(produto['preco']):.2f}"
        
        buttons = [
            {'id': f"add_cart_{produto['id']}", 'title': '🛒 Adicionar'},
            {'id': f"more_details_{produto['id']}", 'title': '+ Detalhes'}
        ]
        
        send_reply_buttons(to_number, from_number, product_text, buttons, conta_id)

def send_talk_to_human_view(conta_id, to_number, from_number):
    """Informa o cliente que um atendente entrará em contato."""
    # Aqui pode-se adicionar lógica para notificar o painel do lojista
    message = "Entendido. Um de nossos atendentes entrará em contato consigo em breve através deste chat. Por favor, aguarde."
    send_text(to_number, from_number, message, conta_id)

