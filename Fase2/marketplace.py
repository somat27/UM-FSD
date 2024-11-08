import random
import socket
import json
import os
import time
import threading
import requests
 
Lock = threading.RLock()

conexoes = {}
produtos_comprados = {}
produtos_comprados_socket = []
threads_heartbeat = {}
taxas_revenda = {}

ARQUIVO_PRODUTORES = 'BasedeDados/Produtores.json'
ARQUIVO_PRODUTOS = 'BasedeDados/Produtos.json'

taxa_padrao = 20.0

COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m' 

def obter_produtores():
    url = "http://193.136.11.170:5001/produtor"
    try:
        response = requests.get(url,timeout=2)
        return response.json() 
    except requests.exceptions.RequestException as e:
        return []

def obter_categorias(ip, porta):
    url = f"http://{ip}:{porta}/categorias"
    try:
        response = requests.get(url,timeout=2)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter categorias: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        return []
    
def obter_produtos_por_categoria(ip, porta, categoria):
    url = f"http://{ip}:{porta}/produtos?categoria={categoria}"
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        return []
    
def comprar_produto(ip, porta, produto, quantidade):
    url = f"http://{ip}:{porta}/comprar/{produto}/{quantidade}"
    try:
        response = requests.get(url)
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Compra realizada com sucesso: {produto} - Quantidade: {quantidade}")
    except requests.exceptions.RequestException as e:
        print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {produto}: {e}")

def listar_subscricoes():
    if not produtos_comprados:
        print(f"{COR_ERRO}Erro: {COR_RESET}Você não tem nenhuma subscrição.")
        return
    print("--- Subscrições ---")
    for nome_produtor, dados_produtor in produtos_comprados.items():
        ip = dados_produtor["ip"]
        porta = dados_produtor["porta"]
        print(f"\nProdutor: {nome_produtor} (IP: {ip}, Porta: {porta})")
        for produto in dados_produtor["produtos"]:
            nome_produto = produto["nome"]
            quantidade = produto["quantidade"]
            preco_compra = produto["preco"]
            taxa_revenda = taxas_revenda.get(nome_produto, taxa_padrao)
            preco_venda = preco_compra + (preco_compra * taxa_revenda / 100)
            print(f" - {nome_produto} - Quantidade: {quantidade}\n\tPreço de Venda: {preco_venda:.2f}€ ( Preço de Compra: {preco_compra:.2f}€ | Taxa de Revenda: {taxa_revenda}%)")

def definir_taxa_revenda():
    if not produtos_comprados:
        print(f"{COR_ERRO}Erro: {COR_RESET}Nenhum produto foi comprado ainda.")
        return
    print("Produtos comprados disponíveis para revenda:")
    produtos_listados = []
    for nome_produtor, dados_produtor in produtos_comprados.items():
        for produto in dados_produtor["produtos"]:
            produtos_listados.append({
                "nome_produtor": nome_produtor,
                "ip": dados_produtor["ip"],
                "porta": dados_produtor["porta"],
                "nome_produto": produto["nome"],
                "quantidade": produto["quantidade"],
                "preco_compra": produto["preco"]
            })
    for i, produto in enumerate(produtos_listados, 1):
        nome_produto = produto["nome_produto"]
        nome_produtor = produto["nome_produtor"]
        quantidade = produto["quantidade"]
        taxa_atual = taxas_revenda.get(nome_produto, 0)
        preco_compra = produto["preco"]
        print(f"{i}. {nome_produto} - Quantidade: {quantidade}, Preço de Compra: {preco_compra}")
    try:
        escolha = int(input("\nEscolha o número do produto para definir a taxa de revenda: "))
        produto_escolhido = produtos_listados[escolha - 1]
        taxa = float(input(f"Digite a taxa de revenda para o produto {produto_escolhido['nome_produto']} (em %): "))
        
        if taxa < 0:
            print(f"{COR_ERRO}Erro: {COR_RESET}A taxa não pode ser negativa.")
            return
        taxas_revenda[produto_escolhido["nome_produto"]] = taxa
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Taxa de revenda de {taxa}% definida para o produto {produto_escolhido['nome_produto']}.")
    except (ValueError, IndexError):
        print(f"{COR_ERRO}Erro: {COR_RESET}Seleção inválida. Tente novamente.")

def conectar_ao_produtor(sock_antigo, ip, porta, nome_produtor):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, porta))
        conexoes[(ip, porta)] = (sock, nome_produtor)
        return sock
    except socket.error:
        return sock_antigo

def definir_taxa_revenda_socket():
    if not produtos_comprados_socket:
        print("Nenhum produto foi comprado ainda.")
        return
    print("Produtos comprados disponíveis para revenda:")
    for i, (id_produtor, nome_produtor, ip, porta, nome_produto, quantidade, preco_compra) in enumerate(produtos_comprados_socket, 1):
        taxa_atual = taxas_revenda.get(nome_produto, 0)
        print(f"{i}. {nome_produto} - Quantidade: {quantidade}, Taxa de Revenda Atual: {taxa_atual}% (Produtor: {nome_produtor})")
    try:
        escolha = int(input("\nEscolha o número do produto para definir a taxa de revenda: "))
        produto_escolhido = produtos_comprados_socket[escolha - 1]
        taxa = float(input(f"Digite a taxa de revenda para o produto {produto_escolhido[4]} (em %): "))
        if taxa < 0:
            print("A taxa não pode ser negativa.")
            return
        taxas_revenda[produto_escolhido[4]] = taxa
        print(f"Taxa de revenda de {taxa}% definida para o produto {produto_escolhido[4]}.")
    except (ValueError, IndexError):
        print("Seleção inválida. Tente novamente.")

def menu_marketplace_Rest():
    while True:
        print("--- Menu Marketplace ---")
        print("1. Lista de Subscrições")
        print("2. Comprar Produtos")
        print("3. Definir Taxa de Revenda")
        print("99. Sair")
        escolha = input("Escolha uma opção: ")
        if escolha == '1':
            listar_subscricoes()
        elif escolha == '2':
            marketplaceRest()
        elif escolha == '3':
            definir_taxa_revenda()
        elif escolha == '99':
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Saindo do Marketplace. Até logo!")
            time.sleep(1)
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida. Tente novamente.")

def testar_porta_ocupada(ip, porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.01)
        try:
            s.bind((ip, porta))
            return True
        except socket.error:
            return False

def testar_conexoes():
    produtores = carregar_json(ARQUIVO_PRODUTORES)
    return [
        (p["ID"], p["IP"], p["Porta"], p["Nome"])
        for p in produtores if testar_porta_ocupada(p["IP"], p["Porta"])
    ]

def remover_produtos_produtor(nome_produtor, ip, porta):
    global produtos_comprados
    global conexoes
    produtos_comprados = [p for p in produtos_comprados if p[0] != nome_produtor]
    if (ip, porta) in conexoes:
        sock, _ = conexoes[(ip, porta)]
        sock.close()
        del conexoes[(ip, porta)]
    print(f"Todos os produtos do produtor {nome_produtor} foram removidos.")

def verificar_conexao_periodicamente(sock, ip, porta, nome_produtor, timeout=30):
    falhas_consec = 0
    while falhas_consec * 2 < timeout:
        with Lock:
            try:
                sock.sendall(b"HEARTBEAT")
                resposta = sock.recv(1024).decode('utf-8')
                if resposta != "OK":
                    raise socket.error("Resposta inesperada do produtor")
                falhas_consec = 0
            except socket.error:
                falhas_consec += 1
                print(f"Perda de conexão com o produtor {nome_produtor} ({ip}:{porta}) - tentativa {falhas_consec}")
                novo_sock = conectar_ao_produtor(sock, ip, porta, nome_produtor)
                if novo_sock and novo_sock != sock:
                    print(f"Conexão restabelecida com o produtor {nome_produtor} ({ip}:{porta})")
                    sock.close()
                    sock = novo_sock
                    conexoes[(ip, porta)] = (sock, nome_produtor)
        time.sleep(2)
    print(f"Produtor {nome_produtor} ({ip}:{porta}) desconectado por mais de {timeout} segundos. Removendo produtos.")
    remover_produtos_produtor(nome_produtor, ip, porta)
    return False

def menu_pesquisa_produtos(categoria_desejada):
    global conexoes
    global produtos_comprados_socket
    global taxa_padrao
    produtores_ativos = testar_conexoes()
    produtos_lista = []
    for _, ip, porta, nome_produtor in produtores_ativos:
        sock_info = conexoes.get((ip, porta))
        if sock_info is None:
            sock = conectar_ao_produtor(None, ip, porta, nome_produtor)
            if sock is None:
                continue
            thread_heartbeat = threading.Thread(target=verificar_conexao_periodicamente, args=(sock, ip, porta, nome_produtor))
            thread_heartbeat.daemon = True
            thread_heartbeat.start()
            threads_heartbeat[(ip, porta)] = thread_heartbeat
        else:
            sock = sock_info[0]
        try:
            with Lock:
                sock.sendall(b"LISTAR_PRODUTOS")
                produtos = sock.recv(4096).decode('utf-8')
            produtos_filtrados = [
                linha for linha in produtos.splitlines()
                if linha.partition(' - ')[2].split('Categoria: ')[1].split(' - ')[0] == categoria_desejada
                and int(linha.partition('Quantidade: ')[2]) > 0
            ]
            for produto in produtos_filtrados:
                produtos_lista.append((nome_produtor, ip, porta, produto))
        except socket.error as e:
            print(f"Erro ao solicitar produtos de {nome_produtor} ({ip}:{porta}): {e}")
            sock.close()
            conexoes.pop((ip, porta), None)
    if not produtos_lista:
        return 1
    print(f"\nCategoria: {categoria_desejada}")
    print("\nLista de produtos disponíveis:")
    produtor_anterior = None
    for i, (nome_produtor, ip, porta, produto) in enumerate(produtos_lista, 1):
        if nome_produtor != produtor_anterior:
            print(f"Produtor: {nome_produtor} (IP: {ip}, Porta: {porta})")
            produtor_anterior = nome_produtor
        print(f"{i}. {produto}")
    escolhas = input("\nEscolha os números dos produtos que deseja comprar (separados por vírgula): ")
    try:
        escolhas_validas = [produtos_lista[int(num.strip()) - 1] for num in escolhas.split(',') if num.strip().isdigit()]
        for nome_produtor, ip, porta, produto in escolhas_validas:
            sock = conexoes[(ip, porta)][0]
            nome_produto = produto.split(' - ')[0]
            preco_compra = float(produto.split('Preço: ')[1].split(' - ')[0])
            id_produtor = next(p[0] for p in testar_conexoes() if p[1] == ip and p[2] == porta)
            while True:
                quantidade = input(f"Digite a quantidade para {nome_produto}: ")
                with Lock:
                    mensagem_compra = f"SUBSCREVER_PRODUTO,{nome_produto},{quantidade}"
                    sock.sendall(mensagem_compra.encode('utf-8'))
                    resposta = sock.recv(1024).decode('utf-8')
                if resposta == "Produto não encontrado ou quantidade insuficiente.":
                    print(resposta)
                else:
                    produtos_comprados_socket.append((id_produtor, nome_produtor, ip, porta, nome_produto, quantidade, preco_compra))
                    taxas_revenda[nome_produto] = taxa_padrao 
                    print(f"Compra confirmada com taxa de revenda padrão de 20% para {nome_produto}.")
                    break
    except (ValueError, IndexError):
        print("Seleção inválida. Tente novamente com números válidos.")

def carregar_json(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r') as f:
            conteudo = f.read() 
            return json.loads(conteudo)
    except FileNotFoundError:
        print(f"Arquivo {caminho_arquivo} não encontrado.")
        return []
    except json.JSONDecodeError:
        print(f"Erro ao decodificar o arquivo JSON {caminho_arquivo}.")
        return []

def gerar_categoria():
    produtos = carregar_json(ARQUIVO_PRODUTOS)
    todas_categorias = list(produtos.keys())
    return random.choice(todas_categorias) if todas_categorias else None

def comprar_produtos():
    produtos = carregar_json(ARQUIVO_PRODUTOS)
    todas_categorias = list(produtos.keys())
    if not todas_categorias:
        print("Nenhuma categoria disponível.")
        return
    print("Categorias disponíveis:")
    for categoria in todas_categorias:
        print(f"- {categoria}")
    while True:
        categoria = input("Escolha uma Categoria (ou digite 0 para voltar): ")
        if categoria == '0':
            print("Voltando ao menu anterior.")
            return  
        if categoria in todas_categorias:
            if menu_pesquisa_produtos(categoria) != 1:
                break
            else:
                print(f"Nenhum produto disponivel na categoria {categoria}. Tente novamente.")
        else:
            print("Categoria inválida. Tente novamente.")

def marketplaceSocket():
    while True:
        categoria = gerar_categoria()
        if menu_pesquisa_produtos(categoria) != 1:
            break
    menu_marketplace_socket()

def listar_subscricoes_socket():
    global taxa_padrao
    produtos_por_produtor = {}
    for id_produto, nome_produtor, ip, porta, nome_produto, quantidade, preco_compra in produtos_comprados_socket:
        if id_produto not in produtos_por_produtor:
            produtos_por_produtor[id_produto] = {
                "nome": nome_produtor,
                "ip": ip,
                "porta": porta,
                "produtos": []
            }
        taxa_revenda = taxas_revenda.get(nome_produto, taxa_padrao)
        preco_venda = preco_compra + (preco_compra * taxa_revenda / 100)
        produtos_por_produtor[id_produto]["produtos"].append((nome_produto, quantidade, preco_compra, taxa_revenda, preco_venda))
    for id_produtor, detalhes in produtos_por_produtor.items():
        print(f"Produtor: {detalhes['nome']} (ID: {id_produtor}, IP: {detalhes['ip']}, Porta: {detalhes['porta']})")
        for nome_produto, quantidade, preco_compra, taxa_revenda, preco_venda in detalhes["produtos"]:
            print(f"  - Nome: {nome_produto}, Quantidade: {quantidade}, Preço de Compra: {preco_compra:.2f}, Preço de Venda: {preco_venda:.2f} ({taxa_revenda}%)")


def menu_marketplace_socket():
    while True:
        print("--- Menu Marketplace ---")
        print("1. Lista de Subscrições")
        print("2. Comprar Produtos")
        print("3. Definir Taxa de Revenda")
        print("99. Sair")
        escolha = input("Escolha uma opção: ")
        if escolha == '1':
            listar_subscricoes_socket()
        elif escolha == '2':
            comprar_produtos()
        elif escolha == '3':
            definir_taxa_revenda_socket()
        elif escolha == '99':
            print("Saindo do Marketplace. Até logo!")
            break
        else:
            print("Opção inválida. Tente novamente.")

def marketplaceRest():
    produtores = obter_produtores()
    categorias_disponiveis = {}
    produtos_disponiveis = []
    global produtos_comprados
    for produtor in produtores:
        categorias = obter_categorias(produtor['ip'], produtor['porta'])
        if categorias:
            print(f"Produtor: {produtor['nome']}")
            for categoria in categorias:
                print(f" - {categoria}")
                if categoria not in categorias_disponiveis:
                    categorias_disponiveis[categoria] = []
                if produtor not in categorias_disponiveis[categoria]:
                    categorias_disponiveis[categoria].append(produtor)
    while True:
        categoria_escolhida = input("\nEscolha uma categoria: ")
        if categoria_escolhida in categorias_disponiveis:
            produtos_disponiveis = []
            for produtor in categorias_disponiveis[categoria_escolhida]:
                try:
                    produtos = obter_produtos_por_categoria(produtor['ip'], produtor['porta'], categoria_escolhida)
                    if produtos:
                        print(f"Produtor: {produtor['nome']}")
                        for index, produto in enumerate(produtos, start=1):
                            if all(key in produto for key in ['categoria', 'produto', 'preco', 'quantidade']):
                                produtos_disponiveis.append({
                                    "produtor": produtor,
                                    "produto": produto
                                })
                                print(f"{index} - {produto['produto']}, Preço: {produto['preco']}€, Quantidade: {produto['quantidade']}")
                            else:
                                print("Erro no formato dos dados do produto:", produto)
                except Exception as e:
                    print(f"Erro ao obter produtos do produtor {produtor['nome']} ({produtor['ip']}:{produtor['porta']}): {e}")
                    continue
            if produtos_disponiveis:
                break
            else:
                print(f"Não há produtos disponíveis na categoria '{categoria_escolhida}'. Por favor, escolha outra categoria.")
        else:
            print(f"A categoria '{categoria_escolhida}' não está disponível. Tente novamente.")
    while True:
        escolha = input("\nEscolha os números dos produtos que deseja comprar (separados por vírgula) ou 'sair' para encerrar: ")
        if escolha.lower() == 'sair':
            marketplaceRest()
        numeros_escolhidos = []
        try:
            numeros_escolhidos = [int(num.strip()) for num in escolha.split(',')]
        except ValueError:
            print("Por favor, insira números válidos.")
            continue
        for num in numeros_escolhidos:
            produto_selecionado = produtos_disponiveis[num - 1]
            produto = produto_selecionado['produto']
            produtor = produto_selecionado['produtor']

            if produto['quantidade'] == 0:
                print(f"Produto {produto['produto']} não disponível.")
            elif 1 <= num <= len(produtos_disponiveis):
                while True:
                    try:
                        quantidade = int(input(f"Digite a quantidade para {produto['produto']} (disponível: {produto['quantidade']}): "))
                        if 1 <= quantidade <= produto['quantidade']:
                            ip = produtor['ip']
                            porta = produtor['porta']
                            nome_produtor = produtor['nome']
                            comprar_produto(ip, porta, produto['produto'], quantidade)
                            if nome_produtor not in produtos_comprados:
                                produtos_comprados[nome_produtor] = {
                                    "id_produtor": produtor.get("id", None),
                                    "ip": ip,
                                    "porta": porta,
                                    "produtos": []
                                }
                            produtos_comprados[nome_produtor]["produtos"].append({
                                "nome": produto['produto'],
                                "quantidade": quantidade,
                                "preco": produto['preco']
                            })
                            print(f"Produto {produto['produto']} comprado com sucesso.")
                            break
                        else:
                            print("Quantidade inválida. Tente novamente.")
                    except ValueError:
                        print("Por favor, insira um número válido.")
        break

def iniciar():
    while True:
        print("\nEscolha o tipo de conexão que deseja utilizar:")
        print("1 - Conexão REST")
        print("2 - Conexão via Socket")
        print("3 - Sair")
        escolha = input("Digite o número correspondente à opção: ")
        if escolha == '1':
            marketplaceRest()
            menu_marketplace_Rest()
            break
        elif escolha == '2':
            marketplaceSocket()
            for sock, _ in conexoes.values():
                sock.close()
            print("Conexões Socket fechadas.")
            break
        elif escolha == '3':
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
   iniciar()