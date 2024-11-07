import socket
import random
import json
import threading
import os
import time
import logging
from flask import Flask, jsonify, request
import contextlib
import io
import requests
import psutil

app = Flask(__name__)

Lock = threading.RLock()

IP_Gestor = '193.136.11.170'
Porta_Default = 1025
Porta_Gestor = 5001
servidor_ativo = True
Info_Produtor = {}
arquivo_produtos = 'BasedeDados/Produtos.json'
CATEGORIAS_PERMITIDAS = ["Fruta", "Livros", "Roupa", "Ferramentas", "Computadores", "Smartphones", "Filmes", "Sapatos"]

COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m'    

def obter_ip_vpn():
  
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address.startswith('10.'):
                return addr.address
    return None

def obter_ip_ethernet():
    
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address.startswith('192.168.'):
                return addr.address
    return None

IP_Default = obter_ip_vpn()
if IP_Default:
    print(f"{COR_SUCESSO}IP VPN detectado: {IP_Default}{COR_RESET}")
else:
    IP_Default = obter_ip_ethernet()
    if IP_Default.startswith('192.168.'):
        print(f"{COR_SUCESSO}VPN desligada. IP Ethernet detectado: {IP_Default}{COR_RESET}")
    else:
        print(f"{COR_ERRO}Nenhum IP da VPN ou Ethernet encontrado. Usando IP padrão: {IP_Default}{COR_RESET}")

def carregar_dados(arquivo):
    with Lock:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

def salvar_dados(arquivo, dados):
    with Lock:
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)

def testar_porta_ocupada(ip, porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.01)
        resultado = s.connect_ex((ip, porta))
        return resultado == 0

def gerar_id_ou_porta(IP, PORTA):
    porta_socket = PORTA
    while True:
        if not testar_porta_ocupada(IP, porta_socket) and not testar_porta_ocupada(IP, porta_socket + 1):
            return porta_socket 
        porta_socket += 2


def registar_produtor(nome_produtor):
    global Info_Produtor, IP_Default, Porta_Default, COR_SUCESSO, COR_ERRO, COR_RESET
    if not IP_Default or not Porta_Default:
        print(f"{COR_ERRO}Erro: {COR_RESET}IP ou Porta padrão não estão definidos.")
        return None
    porta_socket = gerar_id_ou_porta(IP_Default, Porta_Default)
    porta_rest = porta_socket + 1
    Info_Produtor = {
        "Nome": nome_produtor, 
        "IP": IP_Default, 
        "PortaSocket": porta_socket, 
        "PortaRest": porta_rest, 
        "Produtos": []
    }
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Produtor '{nome_produtor}' registado.")
    Post_Produtor = {
        "ip": Info_Produtor["IP"],
        "porta": Info_Produtor["PortaRest"],
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
    with Lock:
        for produto in produtos_selecionados:
            preco = random.uniform(produto['Preco'][0], produto['Preco'][1])
            quantidade = random.randint(produto['Quantidade'][0], produto['Quantidade'][1])
            item_gerado = {"Nome": produto['Nome_Produto'], "Categoria": produto['Categoria'], "Preco": round(preco, 2), "Quantidade": quantidade}
            Info_Produtor['Produtos'].append(item_gerado)
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}{numero_itens} itens gerados.")

def listar_produtos(produtos):
    return [f"{produto['Nome']} - Categoria: {produto.get('Categoria', 'Desconhecida')} - Preço: {produto['Preco']:.2f} - Quantidade: {produto['Quantidade']}" for produto in produtos]

def listar_produtos_endpoint(cliente_socket, id_produtor):
    global Info_Produtor
    produtos = Info_Produtor['Produtos'] if Info_Produtor else []
    resposta = "\n".join(listar_produtos(produtos)) if produtos else "Nenhum produto disponível."
    cliente_socket.sendall(resposta.encode())
def comprar_produto_endpoint(cliente_socket, nome_produto, quantidade):
    global Info_Produtor
    with Lock:
        produto_info = next((prod for prod in Info_Produtor['Produtos'] if prod['Nome'] == nome_produto), None)
        
        if produto_info and produto_info['Quantidade'] >= quantidade:
            produto_info['Quantidade'] -= quantidade 
            resposta = f"Compra realizada com sucesso! Você comprou {quantidade} de {nome_produto}."
            print(f"Cliente comprou {quantidade} de '{nome_produto}'. Novo stock: {produto_info['Quantidade']}")
        else:
            resposta = "Produto não encontrado ou quantidade insuficiente."
            print(f"Compra falhou: Produto '{nome_produto}' não encontrado ou quantidade insuficiente.")
    
    cliente_socket.sendall(resposta.encode()) 


def gerenciar_conexao(cliente_socket, endereco, conexoes):
    try:
        print(f"Conexão estabelecida com {endereco}.")
        with cliente_socket:
            while True:
                data = cliente_socket.recv(1024).decode()
                if not data:
                    break 
                if data.startswith("SUBSCREVER_PRODUTO"):
                    _, nome_produto, quantidade = data.split(',', maxsplit=2)
                    quantidade = int(quantidade)
                    for produto in Info_Produtor["Produtos"]:
                        if produto["Nome"] == nome_produto:
                            produto["Quantidade"] += quantidade
                            break
                    comprar_produto_endpoint(cliente_socket, nome_produto, quantidade)
                elif data.startswith("LISTAR_PRODUTOS"):
                    listar_produtos_endpoint(cliente_socket)
                elif data.startswith("HEARTBEAT"):
                    cliente_socket.sendall("OK".encode('utf-8'))
    except Exception as e:
        print(f"Erro na conexão com {endereco}: {e}")
    finally:
        print(f"Conexão encerrada com {endereco}.")

def listar_produtos():
    if Info_Produtor["Produtos"]:
        print("\n--- Produtos no Marketplace ---")
        for i, produto in enumerate(Info_Produtor["Produtos"], start=1):
            print(f"Produto: {produto['Nome']}, Categoria: {produto['Categoria']}, Quantidade: {produto['Quantidade']}, Preço: {produto['Preco']:.2f}")
    else:
        print("Não há produtos registrados.")

def menu_gestao_produtos():
    global servidor_ativo
    while servidor_ativo:
        print("\n--- Menu de Gestão de Produtos ---")
        print("1. Adicionar produto")
        print("2. Atualizar stock de produto")
        print("3. Remover produto")
        print("4. Listar produtos")
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
        elif opcao == '0':
            print("Saindo do menu de gestão e desligando o servidor...")
            servidor_ativo = False
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida.")
    print("Finalizando o servidor. Aguarde...")
    for thread in threading.enumerate():
        if thread != threading.current_thread():
            thread.join()
    print("Servidor desligado com sucesso.")

def servidor_produtor(Info_Produtor):
    global servidor_ativo
    servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor_socket.bind(('', Info_Produtor['PortaSocket']))
    servidor_socket.listen(5)
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Servidor do Produtor '{Info_Produtor['Nome']}' iniciado no IP {Info_Produtor['IP']} e porta {Info_Produtor['PortaSocket']}.")
    conexoes = []
    threading.Thread(target=menu_gestao_produtos).start()
    while servidor_ativo:
        try:
            servidor_socket.settimeout(1.0)
            try:
                cliente_socket, endereco = servidor_socket.accept()
            except socket.timeout:
                continue
            threading.Thread(target=gerenciar_conexao, args=(cliente_socket, endereco, conexoes)).start()
        except OSError:
            break
    servidor_socket.close()
    print(f"{COR_ERRO}Erro: {COR_RESET}Servidor do Produtor '{Info_Produtor['Nome']}' desligado.")

def iniciar_servidor_flask():
    app.run(host=Info_Produtor["IP"], port=Info_Produtor["PortaRest"], debug=False, use_reloader=False)


def menu_inicial():
    global Info_Produtor
    while True:
        nome_produtor = input("Digite o nome do produtor: ")
        Info_Produtor = registar_produtor(nome_produtor)
        gerar_itens_para_produtor(Info_Produtor, random.randint(3, 5))
        threading.Thread(target=iniciar_servidor_flask).start()
        time.sleep(1)
        threading.Thread(target=servidor_produtor, args=(Info_Produtor,)).start()
        break

@app.route('/categorias', methods=['GET'])
def obter_categorias():
    if "Produtos" in Info_Produtor and Info_Produtor["Produtos"]:
        categorias_disponiveis = set()
        for produto in Info_Produtor["Produtos"]:
            categoria = produto.get('Categoria')
            if categoria:
                categorias_disponiveis.add(categoria)
        return jsonify(list(categorias_disponiveis)), 200
    return jsonify([]), 200

@app.route('/produtos', methods=['GET'])
def obter_produtos_por_categoria():
    categoria = request.args.get('categoria')
    if not categoria:
        return jsonify({"erro": "Parâmetro 'categoria' não fornecido"}), 400
    produtos_encontrados = [
        produto for produto in Info_Produtor.get("Produtos", [])
        if produto.get('Categoria') == categoria  
    ]
    if produtos_encontrados:
        return jsonify([{
            "categoria": produto["Categoria"], 
            "produto": produto["Nome"],  
            "quantidade": produto["Quantidade"],
            "preco": produto["Preco"]
        } for produto in produtos_encontrados]), 200
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
                print(f"{quantidade} unidades de '{produto}' compradas por {preco_total:.2f}€.")
                return jsonify({
                    "sucesso": f"{quantidade} unidades de {produto} compradas",
                    "preco_unitario": preco_unitario,
                    "preco_total": preco_total
                }), 200
            else:
                print(f"Quantidade insuficiente para '{produto}'.")
                return jsonify({"erro": "Quantidade insuficiente"}), 404
        else:
            print(f"Produto '{produto}' não encontrado.")
            return jsonify({"erro": "Produto não encontrado"}), 404
                
if __name__ == "__main__":
    menu_inicial()