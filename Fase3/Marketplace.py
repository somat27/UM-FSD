# ------------ Imports ------------ #
import json
import socket
import time
import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate
# ------------ Imports ------------ #

# ------------ Configuração Global ------------ #
COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m' 
ARQUIVO_PRODUTORES = 'BasedeDados/Produtores.json'
subscricoes_compradas = {}
taxas_revenda = {}     
taxa_padrao = 10.0
# ------------ Configuração Global ------------ #

# ------------ Funções REST ------------ #
def ObterProdutoresRest():
    URL = "http://193.136.11.170:5001/produtor"
    try:
        response = requests.get(URL, timeout=2)
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter produtores REST: {e}")
        return []
    
def ObterCategoriasProdutorRest(IP, PORTA):
    URL = f"http://{IP}:{PORTA}/categorias"
    try:
        response = requests.get(URL, timeout=2)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter categorias via REST: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        return []

def ComprarProdutoRest(produtor_info, nome_produto, quantidade):
    url = f"http://{produtor_info['IP']}:{produtor_info['PORTA']}/comprar/{nome_produto}/{quantidade}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Compra realizada com sucesso para o produto {nome_produto} (Quantidade: {quantidade}).")
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {nome_produto}: Status code {response.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {nome_produto}: {e}")

def ObterCategoriasRest_OLD():
    CategoriasProdutorRestDisponiveis = []
    ProdutoresRest = ObterProdutoresRest()
    for ProdutorRest in ProdutoresRest:
        IP = ProdutorRest['ip']
        PORTA = ProdutorRest['porta']
        CategoriaProdutorDisponivel = None
        for Produtor in CategoriasProdutorRestDisponiveis:
            if Produtor["IP"] == IP and Produtor["PORTA"] == PORTA:
                CategoriaProdutorDisponivel = Produtor
                break
        if not CategoriaProdutorDisponivel:
            CategoriasProdutorRest = ObterCategoriasProdutorRest(IP, PORTA)
            if CategoriasProdutorRest:
                CategoriasProdutorRestDisponiveis.append({
                    "Nome": ProdutorRest['nome'],
                    "IP": IP,
                    "PORTA": PORTA,
                    "Conexao": "REST",
                    "Categorias": set(CategoriasProdutorRest) 
                })
        else:
            CategoriasProdutorRest = ObterCategoriasProdutorRest(IP, PORTA)
            if CategoriasProdutorRest:
                CategoriaProdutorDisponivel["Categorias"].update(CategoriasProdutorRest)
    for Produtor in CategoriasProdutorRestDisponiveis:
        Produtor["Categorias"] = list(Produtor["Categorias"])
    return CategoriasProdutorRestDisponiveis

def ObterCategoriasRest():
    CategoriasProdutorRestDisponiveis = []
    ProdutoresRest = ObterProdutoresRest()
    for ProdutorRest in ProdutoresRest:
        IP = ProdutorRest['ip']
        PORTA = ProdutorRest['porta']
        CategoriasSeguras = ObterCategoriasSegurasProdutorRest(IP, PORTA)
        if CategoriasSeguras:
            CategoriasProdutorRestDisponiveis.append({
                "Nome": ProdutorRest['nome'],
                "IP": IP,
                "PORTA": PORTA,
                "Conexao": "REST",
                "Categorias": CategoriasSeguras
            })
    return CategoriasProdutorRestDisponiveis

def ObterCategoriasSegurasProdutorRest(IP, PORTA):
    URL = f"http://{IP}:{PORTA}/secure/categorias"
    try:
        response = requests.get(URL, timeout=2)
        if response.status_code == 200:
            dados = response.json()
            mensagem = json.dumps(dados["mensagem"])
            assinatura = dados["assinatura"]
            certificado = dados["certificado"]

            if validar_assinatura(mensagem, assinatura, certificado):
                print("1.1")
                return dados["mensagem"]
            else:
                print("1.2")
                return []
        else:
            print(f"Erro ao obter categorias seguras: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar ao produtor REST: {e}")
        return []
    
def ObterProdutosSegurosPorCategoria(IP, PORTA, categoria):
    URL = f"http://{IP}:{PORTA}/secure/produtos?categoria={categoria}"
    try:
        response = requests.get(URL, timeout=2)
        if response.status_code == 200:
            dados = response.json()
            mensagem = json.dumps(dados["mensagem"])
            assinatura = dados["assinatura"]
            certificado = dados["certificado"]

            if validar_assinatura(mensagem, assinatura, certificado):
                print("2.1")
                return dados["mensagem"]
            else:
                print("2.2")
                return []
        else:
            print(f"Erro ao obter produtos seguros: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar ao produtor REST: {e}")
        return []
    
def ComprarProdutoSeguro(IP, PORTA, produto, quantidade):
    URL = f"http://{IP}:{PORTA}/secure/comprar/{produto}/{quantidade}"
    try:
        response = requests.post(URL, timeout=2)
        if response.status_code == 200:
            dados = response.json()
            mensagem = dados["mensagem"]
            assinatura = dados["assinatura"]
            certificado = dados["certificado"]

            if validar_assinatura(mensagem, assinatura, certificado):
                print(f"{COR_SUCESSO}Sucesso: {COR_RESET}{mensagem}")
            else:
                print(f"{COR_ERRO}Erro: {COR_RESET}Assinatura inválida na resposta!")
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao conectar ao produtor REST: {e}")
# ------------ Funções REST ------------ #

# ------------ Funções Socket ------------ #
def ObterProdutoresSocket():
    ProdutoresSocketAtivos = []
    with open(ARQUIVO_PRODUTORES, 'r') as arquivo:
        ArquivoProdutores = json.load(arquivo)
    for ProdutorSocket in ArquivoProdutores:
        ip = ProdutorSocket['IP']
        porta = ProdutorSocket['Porta']
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                resultado = s.connect_ex((ip, porta))
                if resultado == 0:
                    ProdutoresSocketAtivos.append(ProdutorSocket)
        except Exception as e:
            print(f"Erro ao testar conexão com {ip}:{porta}: {e}")
    return ProdutoresSocketAtivos

def ObterCategoriasSocket():
    CategoriasProdutorSocketDisponiveis = []
    ProdutoresSocketAtivos = ObterProdutoresSocket()
    for ProdutorSocket in ProdutoresSocketAtivos:
        IP = ProdutorSocket['IP']
        PORTA = ProdutorSocket['Porta']
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((IP, PORTA))
                s.sendall("LISTAR_CATEGORIAS".encode('utf-8'))
                data = s.recv(1024).decode()
                categorias = data.split("\n")[1:]
                if categorias:
                    CategoriasProdutorSocketDisponiveis.append({
                        "Nome": ProdutorSocket['Nome'],
                        "IP": IP,
                        "PORTA": PORTA,
                        "Conexao": "Socket",
                        "Categorias": categorias
                    })
                else:
                    print(f"Nenhuma categoria encontrada para {ProdutorSocket['Nome']}")
        except Exception as e:
            print(f"Erro ao conectar com {IP}:{PORTA} para obter categorias: {e}")
    return CategoriasProdutorSocketDisponiveis

def ComprarProdutoSocket(produtor_info, nome_produto, quantidade):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(30)
            sock.connect((produtor_info['IP'], produtor_info['PORTA']))
            mensagem_compra = f"SUBSCREVER_PRODUTO,{nome_produto},{quantidade}"
            sock.sendall(mensagem_compra.encode('utf-8'))
            resposta = sock.recv(1024).decode('utf-8')
            if resposta == "OK":
                print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Compra realizada com sucesso para o produto {nome_produto} (Quantidade: {quantidade}).")
            else:
                print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {nome_produto}: {resposta}")
    except socket.timeout:
        print(f"{COR_ERRO}Erro: {COR_RESET}Timeout atingido ao tentar conectar ao produtor {produtor_info['IP']}:{produtor_info['PORTA']}.")
    except Exception as e:
        print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao tentar comprar o produto {nome_produto}: {e}")
# ------------ Funções Socket ------------ #

# ------------ Funções Globais ------------ #
def validar_assinatura(mensagem, assinatura, certificado_pem):
    try:
        certificado = load_pem_x509_certificate(certificado_pem.encode('utf-8'))
        chave_publica = certificado.public_key()
        print(chave_publica)
        chave_publica.verify(
            assinatura.encode('cp437'),
            mensagem.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        return False

def ObterProdutosPorCategoria(Produtor, CategoriaEscolhida):
    Produtos = []
    if Produtor['Conexao'] == "Socket":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                try:
                    s.connect((Produtor['IP'], Produtor['PORTA']))
                    pedido = f"LISTAR_PRODUTOS_CATEGORIA,{CategoriaEscolhida}"
                    s.sendall(pedido.encode('utf-8'))
                    resposta = s.recv(4096).decode('utf-8')
                    Produtos = json.loads(resposta)
                except socket.timeout:
                    print(f"Erro: Timeout atingido ao tentar conectar com o produtor {Produtor['IP']}:{Produtor['PORTA']}")
                except Exception as e:
                    print(f"Erro inesperado ao tentar se conectar com o produtor: {e}")
        except Exception as e:
            print(f"Erro ao se conectar ao produtor {Produtor['IP']}:{Produtor['PORTA']}. Detalhes: {e}")
        return Produtos
    elif Produtor['Conexao'] == "REST":
        return ObterProdutosSegurosPorCategoria(Produtor['IP'], Produtor['PORTA'], CategoriaEscolhida)
        
def ListarProdutos(ProdutosCategoriaEscolhida):
    print("\nProdutos disponíveis para compra:")
    produto_id = 1 
    for produtor_info in ProdutosCategoriaEscolhida:
        print(f"Produtor: {produtor_info['Nome']} ({produtor_info['IP']}:{produtor_info['PORTA']}) - Conexão: {produtor_info['Conexao']}")
        for produto in produtor_info['Produtos']:
            print(f"{produto_id}. Produto: {produto['produto']} - Preço: {produto['preco']} - Quantidade disponível: {produto['quantidade']}")
            produto_id += 1 

def ComprarProdutos_OLD(ProdutosCategoriaEscolhida, produtos_escolhidos):
    produto_id = 1
    produtos_para_exibir = []
    for produtor_info in ProdutosCategoriaEscolhida:
        for produto in produtor_info['Produtos']:
            produto['id'] = produto_id
            produtos_para_exibir.append(produto)
            produto_id += 1
    for id_produto in produtos_escolhidos:
        produto_encontrado = False
        for produto in produtos_para_exibir:
            if id_produto == produto['id']:
                produto_encontrado = True
                if produto['quantidade'] == 0:
                    print(f"Desculpe, {produto['produto']} está fora de estoque.")
                    break
                try:
                    quantidade_desejada = int(input(f"Quantas unidades de {produto['produto']} deseja comprar? "))
                    if quantidade_desejada <= produto['quantidade']:
                        produto['quantidade'] -= quantidade_desejada
                        for produtor_info in ProdutosCategoriaEscolhida:
                            if produto in produtor_info['Produtos']:
                                if produtor_info['Conexao'] == 'Socket':
                                    ComprarProdutoSocket(produtor_info, produto['produto'], quantidade_desejada)
                                elif produtor_info['Conexao'] == 'REST':
                                    ComprarProdutoSeguro(produtor_info['IP'], produtor_info['PORTA'], produto['produto'], 1)
                                nome_produtor = produtor_info["Nome"]
                                ip = produtor_info["IP"]
                                porta = produtor_info["PORTA"]
                                if nome_produtor not in subscricoes_compradas:
                                    subscricoes_compradas[nome_produtor] = {
                                        "ip": ip,
                                        "porta": porta,
                                        "produtos": []
                                    }
                                subscricoes_compradas[nome_produtor]["produtos"].append({
                                    "nome": produto['produto'],
                                    "quantidade": quantidade_desejada,
                                    "preco": produto['preco']
                                })
                                break
                    else:
                        print(f"Desculpe, só temos {produto['quantidade']} unidades disponíveis de {produto['produto']}.")
                except ValueError:
                    print("Quantidade inválida. Por favor, insira um número.")
                break 
        if not produto_encontrado:
            print(f"Produto com ID {id_produto} não encontrado.")

def ComprarProdutos(ProdutosCategoriaEscolhida, produtos_escolhidos):
    produto_id = 1
    produtos_para_exibir = []

    # Associa IDs aos produtos para fácil seleção
    for produtor_info in ProdutosCategoriaEscolhida:
        for produto in produtor_info['Produtos']:
            produto['id'] = produto_id
            produtos_para_exibir.append({"produto": produto, "produtor": produtor_info})
            produto_id += 1

    # Itera sobre os IDs escolhidos
    for id_produto in produtos_escolhidos:
        produto_encontrado = next((p for p in produtos_para_exibir if p["produto"]['id'] == id_produto), None)
        if not produto_encontrado:
            print(f"Produto com ID {id_produto} não encontrado.")
            continue

        produto = produto_encontrado["produto"]
        produtor_info = produto_encontrado["produtor"]

        # Verifica se o produto está disponível em estoque
        if produto['quantidade'] == 0:
            print(f"Desculpe, {produto['produto']} está fora de estoque.")
            continue

        try:
            quantidade_desejada = int(input(f"Quantas unidades de {produto['produto']} deseja comprar? "))
            if quantidade_desejada <= 0:
                print("Quantidade inválida. Por favor, insira um número positivo.")
                continue

            if quantidade_desejada <= produto['quantidade']:
                # Atualiza o estoque local
                produto['quantidade'] -= quantidade_desejada

                # Realiza a compra com o produtor
                if produtor_info['Conexao'] == 'Socket':
                    ComprarProdutoSocket(produtor_info, produto['produto'], quantidade_desejada)
                elif produtor_info['Conexao'] == 'REST':
                    ComprarProdutoSeguro(produtor_info['IP'], produtor_info['PORTA'], produto['produto'], quantidade_desejada)

                # Adiciona a subscrição apenas após a compra bem-sucedida
                nome_produtor = produtor_info["Nome"]
                ip = produtor_info["IP"]
                porta = produtor_info["PORTA"]

                if nome_produtor not in subscricoes_compradas:
                    subscricoes_compradas[nome_produtor] = {
                        "ip": ip,
                        "porta": porta,
                        "produtos": []
                    }

                subscricoes_compradas[nome_produtor]["produtos"].append({
                    "nome": produto['produto'],
                    "quantidade": quantidade_desejada,
                    "preco": produto['preco']
                })

                print(f"{quantidade_desejada} unidades de {produto['produto']} compradas com sucesso.")
            else:
                print(f"Desculpe, só temos {produto['quantidade']} unidades disponíveis de {produto['produto']}.")
        except ValueError:
            print("Quantidade inválida. Por favor, insira um número válido.")

def listar_subscricoes():
    if not subscricoes_compradas:
        print(f"{COR_ERRO}Erro: {COR_RESET}Você não tem nenhuma subscrição.")
        return
    print("--- Subscrições ---")
    for nome_produtor, dados_produtor in subscricoes_compradas.items():
        ip = dados_produtor["ip"]
        porta = dados_produtor["porta"]
        print(f"\nProdutor: {nome_produtor} (IP: {ip}, Porta: {porta})")
        for produto in dados_produtor["produtos"]:
            nome_produto = produto["nome"]
            quantidade = produto["quantidade"]
            preco_compra = float(produto["preco"])
            taxa_revenda = float(taxas_revenda.get(nome_produto, taxa_padrao))
            preco_Com_taxa= round(preco_compra * taxa_revenda, 2)
            preco_venda = preco_compra + (preco_Com_taxa / 100)
            print(f" - {nome_produto} - Quantidade: {quantidade}")
            print(f"\tPreço de Venda: {preco_venda:.2f}€ ( Preço de Compra: {preco_compra:.2f}€ | Taxa de Revenda: {taxa_revenda}%)")

def definir_taxa_revenda():
    try:
        print("\n--- Definir Taxa de Revenda ---")
        print("\nProdutos disponíveis:")
        produto_id = 1
        produtos_para_exibir = []
        for produtor_info in subscricoes_compradas.values():
            for produto in produtor_info["produtos"]:
                print(f"{produto_id}. Produto: {produto['nome']} - Preço de Compra: {produto['preco']}")
                produtos_para_exibir.append(produto)
                produto_id += 1
        produto_numero = int(input("\nDigite o número do produto para definir a taxa de revenda: "))
        if produto_numero < 1 or produto_numero > len(produtos_para_exibir):
            print(f"{COR_ERRO}Erro: {COR_RESET}Número de produto inválido.")
            return
        produto_selecionado = produtos_para_exibir[produto_numero - 1]
        print(f"Você selecionou o produto: {produto_selecionado['nome']}")
        taxa = float(input("Digite a nova taxa de revenda (%): "))
        if taxa < 0:
            print(f"{COR_ERRO}Erro: {COR_RESET}A taxa não pode ser negativa.")
            return
        taxas_revenda[produto_selecionado['nome']] = taxa
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Taxa de revenda para o produto '{produto_selecionado['nome']}' definida para {taxa}%.")
    except ValueError:
        print(f"{COR_ERRO}Erro: {COR_RESET}Valor inválido. Insira um número válido.")

def MenuMarketplace():
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
            main()
        elif escolha == '3':
            definir_taxa_revenda()
        elif escolha == '99':
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Saindo do Marketplace. Até logo!")
            time.sleep(1)
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida. Tente novamente.")

def main():
    ProdutoresComCategoriaEscolhida = []
    ProdutosCategoriaEscolhida = []
    CategoriasDisponiveis = set()
    CategoriasRest = ObterCategoriasRest()
    CategoriasSocket = ObterCategoriasSocket()
    Categorias = CategoriasRest + CategoriasSocket
    for Produtor in Categorias:
        CategoriasDisponiveis.update(Produtor['Categorias'])
    print("Categorias Disponiveis:")
    print(", ".join(CategoriasDisponiveis))
    CategoriaEscolhida = input("Escolha uma categoria: ")
    for Produtor in Categorias:
        if CategoriaEscolhida in Produtor['Categorias']:
            ProdutoresComCategoriaEscolhida.append(Produtor)
    for Produtor in ProdutoresComCategoriaEscolhida:
        Produtos = ObterProdutosPorCategoria(Produtor, CategoriaEscolhida)
        ProdutorComProdutos = {
            'Nome': Produtor['Nome'],
            'IP': Produtor['IP'],
            'PORTA': Produtor['PORTA'],
            'Conexao': Produtor['Conexao'],
            'Produtos': []
        }
        for produto in Produtos:
            ProdutorComProdutos['Produtos'].append(produto)
        ProdutosCategoriaEscolhida.append(ProdutorComProdutos)
    ListarProdutos(ProdutosCategoriaEscolhida)
    try:
        produtos_escolhidos = list(map(int, input("\nDigite os números dos produtos que deseja comprar (separados por vírgula): ").split(',')))
    except ValueError:
        print("Entrada inválida. Por favor, insira números válidos separados por vírgula.")
        return
    ComprarProdutos(ProdutosCategoriaEscolhida, produtos_escolhidos)
    MenuMarketplace()
# ------------ Funções Globais ------------ #

if __name__ == "__main__":
   main()