# ------------ Imports ------------ #
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
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
# ------------ Imports ------------ #

# ------------ Configuração Global ------------ #
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.CRITICAL)
Lock = threading.RLock()
IP_Default = '127.0.0.1'
Porta_Default_Socket = 1025
Porta_Default_Rest = 2025
Servidor_Socket_Ativo = True
Servidor_Rest_Ativo = True
Info_Produtor = {}
arquivo_produtores = 'BasedeDados/Produtores.json'
arquivo_produtos = 'BasedeDados/Produtos.json'
CATEGORIAS_PERMITIDAS = ["Fruta", "Livros", "Roupa", "Ferramentas", "Computadores", "Smartphones", "Filmes", "Sapatos"]
Notificacoes_Rest = []
COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m' 
COR_DEBUG = '\033[94m'
DEBUG = False
# ------------ Configuração Global ------------ #

def debug_print(mensagem):
    if DEBUG:
        print(f"{COR_DEBUG}DEBUG: {COR_RESET}{mensagem}")

# ------------ Routes Rest ------------ #
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
        
@app.route('/secure/categorias', methods=['GET'])
def obter_categorias_seguranca():
    try:
        categorias = list(set(prod['Categoria'] for prod in Info_Produtor.get("Produtos", [])))
        assinatura = assinar_mensagem(categorias)

        certificado_path = "certificado.pem"
        if not os.path.exists(certificado_path):
            raise FileNotFoundError(f"Certificado não encontrado em {certificado_path}")
        certificado = open(certificado_path, "r").read()

        return jsonify({
            "mensagem": categorias,
            "assinatura": assinatura.decode('cp437'),
            "certificado": certificado
        }), 200
    except Exception as e:
        logging.error(f"Erro no endpoint /secure/categorias: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/secure/produtos', methods=['GET'])
def obter_produtos_seguranca():
    try:
        categoria = request.args.get('categoria')
        produtos = [
            {
                "categoria": prod['Categoria'],
                "preco": prod['Preco'],
                "produto": prod['Nome'],
                "quantidade": prod['Quantidade']
            }
            for prod in Info_Produtor.get("Produtos", []) if prod['Categoria'] == categoria
        ]
        assinatura = assinar_mensagem(produtos)
        certificado_path = "certificado.pem"
        if not os.path.exists(certificado_path):
            raise FileNotFoundError(f"Certificado não encontrado em {certificado_path}")
        certificado = open(certificado_path, "r").read()
        
        return jsonify({
            "mensagem": produtos,
            "assinatura": assinatura.decode('cp437'),
            "certificado": certificado
        }), 200 if produtos else 404
    except Exception as e:
            logging.error(f"Erro no endpoint /secure/produtos: {e}")
            return jsonify({"erro": str(e)}), 500
    
@app.route('/secure/comprar/<produto>/<int:quantidade>', methods=['POST'])
def comprar_produto_seguranca(produto, quantidade):
    with Lock:
        certificado_path = "certificado.pem"
        if not os.path.exists(certificado_path):
            raise FileNotFoundError(f"Certificado não encontrado em {certificado_path}")
        certificado = open(certificado_path, "r").read()
        produto_info = next((p for p in Info_Produtor["Produtos"] if p["Nome"] == produto), None)
        if produto_info and produto_info["Quantidade"] >= quantidade:
            produto_info["Quantidade"] -= quantidade
            mensagem = f"{quantidade} unidades de {produto} compradas com sucesso."
            assinatura = assinar_mensagem(mensagem)
            return jsonify({
                "mensagem": mensagem,
                "assinatura": assinatura.decode('cp437'),
                "certificado": certificado
            }), 200
        else:
            mensagem = "Quantidade insuficiente ou produto inexistente."
            assinatura = assinar_mensagem(mensagem)
            return jsonify({
                "mensagem": mensagem,
                "assinatura": assinatura.decode('cp437'),
                "certificado": certificado
            }), 404
# ------------ Routes Rest ------------ #

# ------------ Produtor Rest ------------ #
def registar_produtor_seguro_periodicamente(nome_produtor):
    while True:
        try:
            response = requests.post('http://193.136.11.170:5001/produtor_certificado', json={
                "ip": Info_Produtor["IP"],
                "porta": Info_Produtor["Porta"],
                "nome": nome_produtor,
                "pubKey": open("chave_publica.pem", "r").read()
            })

            if response.status_code in (200, 201):
                certificado = response.text
                with open("certificado.pem", "w") as f:
                    f.write(certificado)
                adicionar_notificacao("Certificado recebido e salvo com sucesso.")
            else:
                print(f"Erro ao registrar produtor: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            debug_print(f"Erro ao tentar registrar o produtor: {e}") 
        time.sleep(60)

def registar_produtor_nao_seguro_periodicamente(nome_produtor):
    while True:
        try:
            response = requests.post('http://193.136.11.170:5001/produtor', json={
                "ip": Info_Produtor["IP"],
                "porta": Info_Produtor["Porta"],
                "nome": nome_produtor
            })

            if response.status_code in (200, 201):
                adicionar_notificacao(f"Registro do produtor '{nome_produtor}' realizado com sucesso.")
            else:
                print(f"Erro ao registrar produtor não seguro: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            debug_print(f"Erro ao tentar registrar o produtor não seguro: {e}")
        time.sleep(60)


def assinar_mensagem(mensagem):
    with open("chave_privada.pem", "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    
    if isinstance(mensagem, list) or isinstance(mensagem, dict):
        mensagem = json.dumps(mensagem).encode('utf-8')
    elif isinstance(mensagem, str):
        mensagem = mensagem.encode('utf-8')
    
    assinatura = private_key.sign(
        mensagem,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return assinatura

def gerar_chaves_rsa():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    with open("chave_privada.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open("chave_publica.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    return private_key, public_key

def registar_produtor_rest_seguro(nome_produtor):
    global Info_Produtor, IP_Default, Porta_Default_Rest
    private_key, public_key = gerar_chaves_rsa()
    porta = gerar_id_ou_porta_rest(IP_Default, Porta_Default_Rest)

    Info_Produtor = {
        "Nome": nome_produtor,
        "IP": IP_Default,
        "Porta": porta,
        "Produtos": []
    }

    Post_Produtor = {
        "ip": Info_Produtor["IP"],
        "porta": Info_Produtor["Porta"],
        "nome": Info_Produtor["Nome"],
        "pubKey": public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    }

    try:
        response = requests.post('http://193.136.11.170:5001/produtor_certificado', json=Post_Produtor)
        if response.status_code in (200, 201):
            certificado = response.text
            with open("certificado.pem", "w") as f:
                f.write(certificado)
            print("Certificado recebido e salvo com sucesso.")
        else:
            print(f"Erro ao registar produtor: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        debug_print(f"Erro de conexão: {e}")
        return None
    return Info_Produtor

def registar_produtor_rest_nao_seguro(nome_produtor):
    global Info_Produtor, IP_Default, Porta_Default_Rest
    porta = gerar_id_ou_porta_rest(IP_Default, Porta_Default_Rest)

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
        if response.status_code in (200, 201):
            print("Produtor Não Seguro registrado com sucesso.")
        else:
            print(f"Erro ao registar produtor não seguro: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        debug_print(f"Erro de conexão: {e}")
        return None
    return Info_Produtor


def gerar_itens_para_produtor_rest(Info_Produtor, numero_itens):  
    produtos = carregar_dados(arquivo_produtos)
    todos_produtos = [dict(produto, Categoria=categoria) for categoria, lista_produtos in produtos.items() for produto in lista_produtos]
    produtos_selecionados = random.sample(todos_produtos, min(numero_itens, len(todos_produtos)))
    for produto in produtos_selecionados:
        preco = random.uniform(produto['Preco'][0], produto['Preco'][1])
        quantidade = random.randint(produto['Quantidade'][0], produto['Quantidade'][1])
        item_gerado = {"Nome": produto['Nome_Produto'], "Categoria": produto['Categoria'], "Preco": round(preco, 2), "Quantidade": quantidade}
        Info_Produtor['Produtos'].append(item_gerado)
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}{numero_itens} itens gerados para o produtor \'{Info_Produtor['Nome']}\'.")

def iniciar_servidor_flask():
    app.run(host=Info_Produtor["IP"], port=Info_Produtor["Porta"], debug=False, use_reloader=False)

def menu_gestao_produtos():
    global Servidor_Rest_Ativo
    while Servidor_Rest_Ativo:
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
            with Lock:
                Info_Produtor["Produtos"].append({
                    "Nome": nome_produto,
                    "Categoria": categoria,
                    "Preco": preco,
                    "Quantidade": quantidade
                })
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Produto '{nome_produto}' adicionado na categoria '{categoria}' com {quantidade} em stock a {preco:.2f}.")
        elif opcao == '2':
            listar_produtos_rest()  
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
            listar_produtos_rest()
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
            listar_produtos_rest()  
            input("\nPressione Enter para voltar ao menu principal...")  
        elif opcao == '5':
            menu_notificacoes()          
        elif opcao == '0':
            print("Saindo do menu de gestão e desligando o servidor...")
            Servidor_Rest_Ativo = False
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida.")
    time.sleep(1)
    print("Finalizando o servidor. Aguarde...")
    time.sleep(1)
    print("Servidor desligado com sucesso.")
    os._exit(0)

def limpar_terminal():
    sistema = platform.system()
    if sistema == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

def gerar_id_ou_porta_rest(IP, PORTA):
    while True:
        if not testar_porta_ocupada(IP, PORTA):
            return PORTA 
        PORTA += 1

def testar_porta_ocupada(ip, porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.01)
        resultado = s.connect_ex((ip, porta))
        return resultado == 0
    
def listar_produtos_rest():
    limpar_terminal()
    if Info_Produtor["Produtos"]:
        print("--- Produtos no Marketplace ---")
        for i, produto in enumerate(Info_Produtor["Produtos"], start=1):
            print(f"Produto: {produto['Nome']}, Categoria: {produto['Categoria']}, Quantidade: {produto['Quantidade']}, Preço: {produto['Preco']:.2f}")
    else:
        print("Não há produtos registrados.")

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

def adicionar_notificacao(mensagem):
    try:
        if request and request.remote_addr:
            ip_cliente = request.remote_addr
            porta_cliente = request.host.split(':')[-1]
            notificacao_completa = f"{mensagem} (IP: {ip_cliente}, Porta: {porta_cliente})"
        else:
            notificacao_completa = mensagem  

        Notificacoes_Rest.append(notificacao_completa)
        print(f"Notificação adicionada: {notificacao_completa}")
    except RuntimeError: 
        Notificacoes_Rest.append(mensagem)
        print(f"Notificação de sistema adicionada: {mensagem}")

def menu_rest_seguro():
    global Info_Produtor
    while True:
        nome_produtor = input("Digite o nome do produtor REST Seguro: ")
        Info_Produtor = registar_produtor_rest_seguro(nome_produtor)
        gerar_itens_para_produtor_rest(Info_Produtor, random.randint(3, 5))
        threading.Thread(target=registar_produtor_seguro_periodicamente, args=(nome_produtor,), daemon=True).start()
        threading.Thread(target=iniciar_servidor_flask).start()
        time.sleep(3)
        threading.Thread(target=menu_gestao_produtos).start()
        break

def menu_rest_nao_seguro():
    global Info_Produtor
    while True:
        nome_produtor = input("Digite o nome do produtor REST Não Seguro: ")
        Info_Produtor = registar_produtor_rest_nao_seguro(nome_produtor)
        gerar_itens_para_produtor_rest(Info_Produtor, random.randint(3, 5))
        threading.Thread(target=registar_produtor_nao_seguro_periodicamente, args=(nome_produtor,), daemon=True).start()
        threading.Thread(target=iniciar_servidor_flask).start()
        time.sleep(3)
        threading.Thread(target=menu_gestao_produtos).start()
        break

# ------------ Produtor Rest ------------ #

# ------------ Produtor Socket ------------ #
def menu_socket(IP_Default):
    while True:
        opcao = input("\n--- Menu Inicial ---\n1. Criar novo produtor\n2. Iniciar sessão com produtor existente\n99. Sair\nEscolha uma opção: ")
        if opcao == '1':
            nome_produtor = input("Digite o nome do novo produtor: ")
            id_produtor, porta = registar_produtor_socket(nome_produtor, IP_Default)
            gerar_itens_para_produtor_socket(id_produtor, random.randint(3, 5))
            servidor_produtor(nome_produtor, id_produtor, porta, IP_Default)
            break
        elif opcao == '2':
            nome_produtor, id_produtor, porta, ip = iniciar_sessao_produtor()
            if nome_produtor and id_produtor:
                servidor_produtor(nome_produtor, id_produtor, porta, ip)
            break
        elif opcao == '99':
            print("Saindo...")
            break

def salvar_dados(arquivo, dados):
    with Lock:
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)

def gerar_id_ou_porta_socket(lista, chave, valor_default):
    valores = [int(item[chave]) for item in lista if item.get(chave) and str(item[chave]).isdigit()]
    return max(valores) + 1 if valores else valor_default

def registar_produtor_socket(nome_produtor, IP_Default):
    produtores = carregar_dados(arquivo_produtores)
    id_produtor = gerar_id_ou_porta_socket(produtores, 'ID', 1)
    porta_socket = gerar_id_ou_porta_socket(produtores, 'Porta', Porta_Default_Socket)
    novo_produtor = {"ID": id_produtor, "Nome": nome_produtor, "IP": IP_Default, "Porta": porta_socket, "Produtos": []}
    produtores.append(novo_produtor)
    salvar_dados(arquivo_produtores, produtores)
    print(f"Produtor '{nome_produtor}' registrado com ID {id_produtor} e Porta {porta_socket}.")
    return id_produtor, porta_socket

def gerar_itens_para_produtor_socket(id_produtor, numero_itens):   
    produtos = carregar_dados(arquivo_produtos)
    produtores = carregar_dados(arquivo_produtores)
    todos_produtos = [dict(produto, Categoria=categoria) for categoria, lista_produtos in produtos.items() for produto in lista_produtos]
    produtos_selecionados = random.sample(todos_produtos, min(numero_itens, len(todos_produtos)))
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    with Lock:
        for produto in produtos_selecionados:
            item_gerado = {
                "produto": produto['Nome_Produto'],
                "categoria": produto['Categoria'],
                "preco": round(random.uniform(produto['Preco'][0], produto['Preco'][1]), 2),  
                "quantidade": random.randint(produto['Quantidade'][0], produto['Quantidade'][1]) 
            }
            produtor['Produtos'].append(item_gerado)
        salvar_dados(arquivo_produtores, produtores)
    print(f"{numero_itens} itens gerados.")

def listar_produtos_socket(produtos):
    return [f"{produto['Nome']} - Categoria: {produto.get('Categoria', 'Desconhecida')} - Preço: {produto['Preco']:.2f} - Quantidade: {produto['Quantidade']}" for produto in produtos]

def adicionar_stock_periodicamente(id_produtor):
    intervalo_tempo = 60
    while True:
        time.sleep(intervalo_tempo)
        produtores = carregar_dados(arquivo_produtores)
        produtor = next((p for p in produtores if p["ID"] == id_produtor), None)
        if produtor and produtor['Produtos']:
            num_produtos_para_atualizar = random.randint(1, len(produtor['Produtos']))
            produtos_para_atualizar = random.sample(produtor['Produtos'], num_produtos_para_atualizar)
            with Lock:
                for produto in produtos_para_atualizar:
                    stock_atual = produto.get('quantidade', 0)
                    quantidade_maxima = random.randint(100, 200)
                    novo_stock = min(stock_atual + random.randint(5, 20), quantidade_maxima)
                    produto['quantidade'] = novo_stock
                    print(f"Stock de '{produto['produto']}' atualizado para {novo_stock} [Antigo: {stock_atual}].")     
            salvar_dados(arquivo_produtores, produtores)

def listar_produtos_endpoint(cliente_socket, id_produtor):
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    produtos = produtor['Produtos'] if produtor else []
    resposta = "\n".join(listar_produtos_socket(produtos)) if produtos else "Nenhum produto disponível."
    cliente_socket.sendall(resposta.encode())

def comprar_produto_endpoint(cliente_socket, id_produtor, nome_produto, quantidade):
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    with Lock:
        produto_info = next((prod for prod in produtor['Produtos'] if prod['produto'] == nome_produto), None)
        if produto_info and produto_info['quantidade'] >= quantidade:
            produto_info['quantidade'] -= quantidade
            salvar_dados(arquivo_produtores, produtores)
            resposta = "OK"
            print(f"Cliente comprou {quantidade} de '{nome_produto}'.")
        else:
            resposta = "Produto não encontrado ou quantidade insuficiente."
            print(f"Compra falhou: Produto '{nome_produto}' não encontrado ou quantidade insuficiente.")
    cliente_socket.sendall(resposta.encode())

def listar_categorias(cliente_socket, id_produtor):
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    if produtor:
        categorias = set()
        for produto in produtor['Produtos']:
            categorias.add(produto['categoria'])
        categorias = list(categorias)
        if categorias:
            resposta = "Categorias disponíveis:\n" + "\n".join(categorias)
        else:
            resposta = "Nenhuma categoria disponível."
    else:
        resposta = f"Produtor com ID {id_produtor} não encontrado."
    cliente_socket.sendall(resposta.encode('utf-8'))

def listar_produtos_por_categoria(cliente_socket, id_produtor, categoria):
    try:
        with open('BasedeDados/Produtores.json', 'r') as file:
            produtores = json.load(file)
        produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
        if produtor:
            produtos_encontrados = []
            for produto in produtor['Produtos']:
                if produto['categoria'].strip().lower() == categoria.strip().lower():
                    produto_info = {
                        "categoria": produto['categoria'],
                        "produto": produto['produto'],
                        "quantidade": produto['quantidade'],
                        "preco": f"{produto['preco']}"
                    }
                    produtos_encontrados.append(produto_info)
            if produtos_encontrados:
                resposta = json.dumps(produtos_encontrados, ensure_ascii=False)
            else:
                resposta = json.dumps({"erro": f"Não há produtos na categoria {categoria} para o produtor {id_produtor}."}, ensure_ascii=False)
        else:
            resposta = json.dumps({"erro": f"Produtor com ID {id_produtor} não encontrado."}, ensure_ascii=False)
        cliente_socket.sendall(resposta.encode('utf-8'))
    except Exception as e:
        debug_print(f"Erro ao listar produtos por categoria: {e}")
        cliente_socket.sendall(f"Erro ao listar produtos: {e}".encode('utf-8'))

def gerenciar_conexao(cliente_socket, endereco, conexoes, produtos_marketplace, id_produtor):
    try:
        print(f"Conexão estabelecida com {endereco}.")
        with cliente_socket:
            while True:
                data = cliente_socket.recv(1024).decode()
                if not data:
                    break
                print(f"Mensagem recebida: {data}")
                if data.startswith("LISTAR_PRODUTOS_CATEGORIA"):
                    try:
                        _, categoria = data.split(",", maxsplit=1)
                        print(f"Listar produtos na categoria: {categoria.strip()}")
                        listar_produtos_por_categoria(cliente_socket, id_produtor, categoria.strip())
                    except Exception as e:
                        debug_print(f"Erro ao processar LISTAR_PRODUTOS_CATEGORIA: {e}")
                else:
                    if data.startswith("SUBSCREVER_PRODUTO"):
                        try:
                            _, nome_produto, quantidade = data.split(',', maxsplit=2)
                            quantidade = int(quantidade.strip())
                            produtos_marketplace.setdefault(endereco, []).append((nome_produto.strip(), quantidade))
                            comprar_produto_endpoint(cliente_socket, id_produtor, nome_produto.strip(), quantidade)
                        except Exception as e:
                            debug_print(f"Erro ao processar SUBSCREVER_PRODUTO: {e}")
                    elif data.startswith("LISTAR_PRODUTOS"):
                        listar_produtos_endpoint(cliente_socket, id_produtor)
                    elif data.startswith("HEARTBEAT"):
                        cliente_socket.sendall("OK".encode('utf-8'))
                    elif data.startswith("LISTAR_CATEGORIAS"):
                        listar_categorias(cliente_socket, id_produtor)     
    except Exception as e:
        debug_print(f"Erro na conexão com {endereco}: {e}")
    finally:
        print(f"Conexão encerrada com {endereco}.")
        cliente_socket.close()

def servidor_produtor(nome_produtor, id_produtor, porta, ip):
    global Servidor_Socket_Ativo
    servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor_socket.bind(('', porta))
    servidor_socket.listen(5)
    print(f"Servidor do Produtor '{nome_produtor}' iniciado no IP {ip} e porta {porta}.")
    conexoes = []
    produtos_marketplace = {}
    threading.Thread(target=adicionar_stock_periodicamente, args=(id_produtor,)).start()
    while Servidor_Socket_Ativo:
        try:
            servidor_socket.settimeout(1.0)
            try:
                cliente_socket, endereco = servidor_socket.accept()
            except socket.timeout:
                continue
            threading.Thread(target=gerenciar_conexao, args=(cliente_socket, endereco, conexoes, produtos_marketplace, id_produtor)).start()
        except OSError:
            break
    servidor_socket.close()
    print(f"Servidor do Produtor '{nome_produtor}' desligado.")

def iniciar_sessao_produtor():
    nome_produtor = input("Digite o nome do produtor: ")
    id_produtor = input("Digite o ID do produtor: ")
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['Nome'] == nome_produtor and str(p['ID']) == id_produtor), None)
    if produtor:
        print(f"Bem-vindo de volta, {produtor['Nome']}!")
        return produtor['Nome'], produtor['ID'], produtor['Porta'], produtor['IP']
    else:
        print("Produtor não encontrado.")
        return None, None, None
# ------------ Produtor Socket ------------ #

# ------------ Funções Globais ------------ #
def obter_ip_vpn():
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address.startswith('10.'):
                return addr.address
    return None

def carregar_dados(arquivo):
    with Lock:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

def menu_inicial(IP_Default):
    while True:
        print("\nSelecione o tipo de Produtor para iniciar:")
        print("1. Produtor REST Seguro")
        print("2. Produtor REST Não Seguro")
        print("3. Produtor Socket")
        print("4. Sair")
        escolha = input("Insira o número da opção desejada: ").strip()

        if escolha == "1":
            menu_rest_seguro()
            break
        elif escolha == "2":
            menu_rest_nao_seguro()
            break
        elif escolha == "3":
            menu_socket(IP_Default)
            break
        elif escolha == "4":
            print("Encerrando o programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")

# ------------ Funções Globais ------------ #

if __name__ == "__main__":
    IP_Default = obter_ip_vpn()
    if IP_Default:
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}IP VPN detectado: {IP_Default}")
        menu_inicial(IP_Default)
    else:
        print(f"{COR_ERRO}Erro: {COR_RESET}IP VPN não detectado, tente outra vez!")