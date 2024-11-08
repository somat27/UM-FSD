import socket
import random
import json
import threading
import os
import platform
import logging
from flask import Flask, jsonify, request
import requests
import psutil
import time

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.CRITICAL)

Lock = threading.RLock()

IP_Default = '127.0.0.1'
IP_Gestor = '193.136.11.170'
Porta_Default = 1025
Porta_Gestor = 5001
Servidor_Ativo = True
Info_Produtor = {}
arquivo_produtos = 'BasedeDados/Produtos.json'
CATEGORIAS_PERMITIDAS = ["Fruta", "Livros", "Roupa", "Ferramentas", "Computadores", "Smartphones", "Filmes", "Sapatos"]
Notificacoes_Rest = []

COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m'    

def limpar_terminal():
    sistema = platform.system()
    if sistema == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

def obter_ip_vpn():
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address.startswith('10.'):
                return addr.address
    return None

def carregar_dados(arquivo):
    if os.path.exists(arquivo):
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def testar_porta_ocupada(ip, porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.01)
        resultado = s.connect_ex((ip, porta))
        return resultado == 0

def gerar_id_ou_porta(IP, PORTA):
    while True:
        if not testar_porta_ocupada(IP, PORTA):
            return PORTA 
        PORTA += 1

def registar_produtor(nome_produtor):
    global Info_Produtor, IP_Default, Porta_Default, COR_SUCESSO, COR_ERRO, COR_RESET
    if not IP_Default or not Porta_Default:
        print(f"{COR_ERRO}Erro: {COR_RESET}IP ou Porta padrão não estão definidos.")
        return None
    porta = gerar_id_ou_porta(IP_Default, Porta_Default)
    Info_Produtor = {
        "Nome": nome_produtor, 
        "IP": IP_Default, 
        "Porta": porta, 
        "Produtos": []
    }
    Post_Produtor = {
        "ip": Info_Produtor["IP"],
        "porta": Info_Produtor["Porta"],
        "nome": Info_Produtor["Nome"]
    }
    try:
        response = requests.post('http://193.136.11.170:5001/produtor', json=Post_Produtor)
        if response.status_code == 200:
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}A informação do produtor foi atualizada com sucesso.")
        elif response.status_code == 201:
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}O novo produtor foi registado com sucesso.")
        elif response.status_code == 400:
            print(f"{COR_ERRO}Erro: {COR_RESET}Pedido inválido. O servidor não conseguiu processar.")
        else:
            print(f"{COR_ERRO}Erro inesperado: {COR_RESET}Código de status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"{COR_ERRO}Erro de conexão: {COR_RESET}{e}")
    return Info_Produtor

def gerar_itens_para_produtor(Info_Produtor, numero_itens):  
    produtos = carregar_dados(arquivo_produtos)
    todos_produtos = [dict(produto, Categoria=categoria) for categoria, lista_produtos in produtos.items() for produto in lista_produtos]
    produtos_selecionados = random.sample(todos_produtos, min(numero_itens, len(todos_produtos)))
    for produto in produtos_selecionados:
        preco = random.uniform(produto['Preco'][0], produto['Preco'][1])
        quantidade = random.randint(produto['Quantidade'][0], produto['Quantidade'][1])
        item_gerado = {"Nome": produto['Nome_Produto'], "Categoria": produto['Categoria'], "Preco": round(preco, 2), "Quantidade": quantidade}
        Info_Produtor['Produtos'].append(item_gerado)
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}{numero_itens} itens gerados para o produtor \'{Info_Produtor['Nome']}\'.")

def listar_produtos():
    limpar_terminal()
    if Info_Produtor["Produtos"]:
        print("--- Produtos no Marketplace ---")
        for i, produto in enumerate(Info_Produtor["Produtos"], start=1):
            print(f"Produto: {produto['Nome']}, Categoria: {produto['Categoria']}, Quantidade: {produto['Quantidade']}, Preço: {produto['Preco']:.2f}")
    else:
        print("Não há produtos registrados.")

def menu_gestao_produtos():
    global Servidor_Ativo
    while Servidor_Ativo:
        limpar_terminal()
        print("--- Menu de Gestão de Produtos ---")
        print("1. Adicionar produto")
        print("2. Atualizar stock de produto")
        print("3. Remover produto")
        print("4. Listar produtos")
        print("5. Notificações Flask")
        print("0. Sair do menu de gestão")
        opcao = input("Escolha uma opção: ")
        if opcao == '1':
            nome_produto = input("Nome do produto: ")
            print("Escolha uma categoria:")
            for i, categoria in enumerate(CATEGORIAS_PERMITIDAS, 1):
                print(f"{i}. {categoria}")
            try:
                categoria_index = int(input("Número da categoria: ")) - 1
                if 0 <= categoria_index < len(CATEGORIAS_PERMITIDAS):
                    categoria = CATEGORIAS_PERMITIDAS[categoria_index]
                else:
                    print(f"{COR_ERRO}Erro: {COR_RESET}Categoria inválida.")
                    continue
            except ValueError:
                print(f"{COR_ERRO}Erro: {COR_RESET}Entrada inválida. Selecione um número.")
                continue
            preco = float(input("Preço do produto: "))
            quantidade = int(input("Quantidade em stock: "))
            Info_Produtor["Produtos"].append({
                "Nome": nome_produto,
                "Categoria": categoria,
                "Preco": preco,
                "Quantidade": quantidade
            })
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Produto '{nome_produto}' adicionado na categoria '{categoria}' com {quantidade} em stock a {preco:.2f}.")
        elif opcao == '2':
            listar_produtos()  
            nome_produto = input("Nome do produto a atualizar: ")
            produto_encontrado = False
            for produto in Info_Produtor["Produtos"]:
                if produto["Nome"] == nome_produto:
                    quantidade = int(input("Nova quantidade em stock: "))
                    produto["Quantidade"] = quantidade
                    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Stock do produto '{nome_produto}' atualizado para {quantidade}.")
                    produto_encontrado = True
                    break
            if not produto_encontrado:
                print(f"{COR_ERRO}Erro: {COR_RESET}Produto '{nome_produto}' não encontrado.")
        elif opcao == '3':
            listar_produtos()
            nome_produto = input("Nome do produto a remover: ")
            produto_encontrado = False
            for produto in Info_Produtor["Produtos"]:
                if produto["Nome"] == nome_produto:
                    Info_Produtor["Produtos"].remove(produto)
                    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Produto '{nome_produto}' removido.")
                    produto_encontrado = True
                    break
            if not produto_encontrado:
                print(f"{COR_ERRO}Erro: {COR_RESET}Produto '{nome_produto}' não encontrado.")
        elif opcao == '4':
            listar_produtos()  
            input("\nPressione Enter para voltar ao menu principal...")  
        elif opcao == '5':
            menu_notificacoes()          
        elif opcao == '0':
            print("Saindo do menu de gestão e desligando o servidor...")
            Servidor_Ativo = False
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida.")
    time.sleep(1)
    print("Finalizando o servidor. Aguarde...")
    time.sleep(1)
    print("Servidor desligado com sucesso.")

def iniciar_servidor_flask():
    app.run(host=Info_Produtor["IP"], port=Info_Produtor["Porta"], debug=False, use_reloader=False)

def menu_notificacoes():
    limpar_terminal()
    global Notificacoes_Rest
    print("--- Notificações do Flask ---")
    if Notificacoes_Rest:
        for msg in Notificacoes_Rest:
            print(f"- {msg}")
    else:
        print("Não há notificações disponíveis.")
    input("\nPressione Enter para voltar ao menu principal...")

def menu_inicial():
    global Info_Produtor
    while True:
        nome_produtor = input("Digite o nome do produtor: ")
        Info_Produtor = registar_produtor(nome_produtor)
        gerar_itens_para_produtor(Info_Produtor, random.randint(3, 5))
        threading.Thread(target=iniciar_servidor_flask).start()
        time.sleep(3)
        threading.Thread(target=menu_gestao_produtos).start()
        break

def adicionar_notificacao(mensagem):
    ip_cliente = request.remote_addr
    porta_cliente = request.host.split(':')[-1]
    notificacao_completa = f"{mensagem} (IP: {ip_cliente}, Porta: {porta_cliente})"
    Notificacoes_Rest.append(notificacao_completa)

@app.route('/categorias', methods=['GET'])
def obter_categorias():
    if "Produtos" in Info_Produtor and Info_Produtor["Produtos"]:
        categorias_disponiveis = set()
        for produto in Info_Produtor["Produtos"]:
            categoria = produto.get('Categoria')
            if categoria:
                categorias_disponiveis.add(categoria)
        adicionar_notificacao("Categorias obtidas com sucesso.")
        return jsonify(list(categorias_disponiveis)), 200
    else:
        adicionar_notificacao("Não há produtos registados para obter categorias.")
        return jsonify([]), 200

@app.route('/produtos', methods=['GET'])
def obter_produtos_por_categoria():
    categoria = request.args.get('categoria')
    if not categoria:
        adicionar_notificacao("Parâmetro 'categoria' não fornecido.")
        return jsonify({"erro": "Parâmetro 'categoria' não fornecido"}), 400
    produtos_encontrados = [
        produto for produto in Info_Produtor.get("Produtos", [])
        if produto.get('Categoria') == categoria  
    ]
    if produtos_encontrados:
        adicionar_notificacao(f"Produtos encontrados para a categoria '{categoria}'.")
        return jsonify([{
            "categoria": produto["Categoria"], 
            "produto": produto["Nome"],  
            "quantidade": produto["Quantidade"],
            "preco": produto["Preco"]
        } for produto in produtos_encontrados]), 200
    else:
        adicionar_notificacao(f"Nenhum produto encontrado na categoria '{categoria}'.")
        return jsonify({"erro": "Categoria inexistente"}), 404

@app.route('/comprar/<produto>/<int:quantidade>', methods=['GET'])
def comprar_produto(produto, quantidade):
    with Lock: 
        produto_info = next((prod for prod in Info_Produtor['Produtos'] if prod['Nome'] == produto), None)
        if produto_info:
            if produto_info["Quantidade"] >= quantidade:
                preco_unitario = produto_info["Preco"]
                preco_total = preco_unitario * quantidade
                produto_info["Quantidade"] -= quantidade
                adicionar_notificacao(f"{quantidade} unidades de '{produto}' compradas por {preco_total:.2f}€.")
                return jsonify({
                    "sucesso": f"{quantidade} unidades de {produto} compradas",
                    "preco_unitario": preco_unitario,
                    "preco_total": preco_total
                }), 200
            else:
                adicionar_notificacao(f"Quantidade insuficiente para '{produto}'.")
                return jsonify({"erro": "Quantidade insuficiente"}), 404
        else:
            adicionar_notificacao(f"Produto '{produto}' não encontrado.")
            return jsonify({"erro": "Produto não encontrado"}), 404
                
if __name__ == "__main__":
    IP_Default = obter_ip_vpn()
    if IP_Default:
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}IP VPN detectado: {IP_Default}")
        menu_inicial()
    else:
        print(f"{COR_ERRO}Erro: {COR_RESET}IP VPN não detectado, tente outra vez!")