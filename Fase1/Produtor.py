import socket
import random
import json
import threading
import os
import time

Lock = threading.RLock()

IP = '127.0.0.1'
Porta_Default = 1025

servidor_ativo = True
arquivo_produtores = 'BasedeDados/Produtores.json'
arquivo_produtos = 'BasedeDados/Produtos.json'

def carregar_dados(arquivo):
    """
    Carrega os dados a partir de um arquivo JSON. 
    Usa um bloqueio (RLock) para garantir que múltiplas threads não acessem o arquivo ao mesmo tempo. 
    Retorna uma lista de dados ou uma lista vazia se o arquivo não existir.
    """
    with Lock:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

def salvar_dados(arquivo, dados):
    """
    Salva dados no arquivo especificado em formato JSON. 
    Usa um bloqueio (RLock) para garantir a integridade durante operações simultâneas de escrita por múltiplas threads.
    """
    with Lock:
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)

def gerar_id_ou_porta(lista, chave, valor_default):
    """
    Gera um novo ID ou número de porta. 
    Verifica a lista fornecida para encontrar o maior valor de uma chave específica (ID ou Porta) e retorna o próximo número sequencial. 
    Se não houver valores, retorna o valor default fornecido.
    """
    valores = [int(item[chave]) for item in lista if item.get(chave) and str(item[chave]).isdigit()]
    return max(valores) + 1 if valores else valor_default

def registar_produtor(nome_produtor):
    """
    Registra um novo produtor, gerando um ID e uma porta para ele. 
    Armazena as informações do produtor no arquivo de produtores e retorna o ID e a porta gerados. 
    Também imprime no console os detalhes do novo produtor.
    """
    produtores = carregar_dados(arquivo_produtores)
    id_produtor = gerar_id_ou_porta(produtores, 'ID', 1)
    porta_socket = gerar_id_ou_porta(produtores, 'Porta', Porta_Default)
    novo_produtor = {"ID": id_produtor, "Nome": nome_produtor, "IP": IP, "Porta": porta_socket, "Produtos": []}
    produtores.append(novo_produtor)
    salvar_dados(arquivo_produtores, produtores)
    print(f"Produtor '{nome_produtor}' registrado com ID {id_produtor} e Porta {porta_socket}.")
    return id_produtor, porta_socket, IP

def gerar_itens_para_produtor(id_produtor, numero_itens):
    """
    Gera um número especificado de itens aleatórios (produtos) para um produtor existente e os adiciona à lista de produtos do produtor. 
    Usa um bloqueio para garantir a segurança na modificação dos dados. 
    Após a geração, salva os produtos atualizados no arquivo e imprime uma mensagem indicando a geração dos itens.
    """     
    produtos = carregar_dados(arquivo_produtos)
    produtores = carregar_dados(arquivo_produtores)
    todos_produtos = [dict(produto, Categoria=categoria) for categoria, lista_produtos in produtos.items() for produto in lista_produtos]
    produtos_selecionados = random.sample(todos_produtos, min(numero_itens, len(todos_produtos)))
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    with Lock:
        for produto in produtos_selecionados:
            preco = random.uniform(produto['Preco'][0], produto['Preco'][1])
            quantidade = random.randint(produto['Quantidade'][0], produto['Quantidade'][1])
            item_gerado = {"Nome": produto['Nome_Produto'], "Categoria": produto['Categoria'], "Preco": round(preco, 2), "Quantidade": quantidade}
            produtor['Produtos'].append(item_gerado)
        salvar_dados(arquivo_produtores, produtores)
    print(f"{numero_itens} itens gerados.")

def listar_produtos(produtos):
    """
    Gera uma lista formatada de strings, representando cada produto (nome, categoria, preço e quantidade). 
    Retorna a lista pronta para ser exibida.
    """
    return [f"{produto['Nome']} - Categoria: {produto.get('Categoria', 'Desconhecida')} - Preço: {produto['Preco']:.2f} - Quantidade: {produto['Quantidade']}" for produto in produtos]

def adicionar_stock_periodicamente(id_produtor):
    """
    Atualiza o stock de produtos periodicamente (a cada 30 segundos). 
    Escolhe aleatoriamente um número de produtos do produtor para aumentar o stock, garantindo que o valor não ultrapasse o limite máximo. 
    Usa um bloqueio para garantir que o stock seja atualizado corretamente em cenários de concorrência e imprime uma mensagem a cada atualização.
    """
    intervalo_tempo = 30
    while True:
        time.sleep(intervalo_tempo)
        produtores = carregar_dados(arquivo_produtores)
        produtor = next((p for p in produtores if p["ID"] == id_produtor), None)
        if produtor and produtor['Produtos']:
            num_produtos_para_atualizar = random.randint(1, len(produtor['Produtos']))
            produtos_para_atualizar = random.sample(produtor['Produtos'], num_produtos_para_atualizar)
            with Lock:
                for produto in produtos_para_atualizar:
                    stock_atual = produto.get('Quantidade', 0)
                    quantidade_maxima = random.randint(100, 200)
                    novo_stock = min(stock_atual + random.randint(5, 20), quantidade_maxima)
                    produto['Quantidade'] = novo_stock
                    print(f"Stock de '{produto['Nome']}' atualizado para {novo_stock} [Antigo: {stock_atual}].")     
            salvar_dados(arquivo_produtores, produtores)

def listar_produtos_endpoint(cliente_socket, id_produtor):
    """
    Envia a listagem de produtos de um produtor específico para o cliente conectado via socket. 
    Carrega os dados do produtor e formata os produtos antes de enviar. 
    Imprime uma mensagem no console indicando que os dados foram enviados.
    """
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    produtos = produtor['Produtos'] if produtor else []
    resposta = "\n".join(listar_produtos(produtos)) if produtos else "Nenhum produto disponível."
    cliente_socket.sendall(resposta.encode())

def comprar_produto_endpoint(cliente_socket, id_produtor, nome_produto, quantidade):
    """
    Permite que o cliente compre uma quantidade especificada de um produto de um produtor. 
    Verifica se há estoque suficiente e, se houver, reduz a quantidade disponível. 
    Usa um bloqueio para garantir a consistência dos dados durante a compra. 
    Responde ao cliente com uma mensagem de sucesso ou erro e imprime o resultado da operação.
    """
    produtores = carregar_dados(arquivo_produtores)
    produtor = next((p for p in produtores if p['ID'] == id_produtor), None)
    with Lock:
        produto_info = next((prod for prod in produtor['Produtos'] if prod['Nome'] == nome_produto), None)
        if produto_info and produto_info['Quantidade'] >= quantidade:
            produto_info['Quantidade'] -= quantidade
            salvar_dados(arquivo_produtores, produtores)
            resposta = f"Compra realizada com sucesso! Você comprou {quantidade} de {nome_produto}."
            print(f"Cliente comprou {quantidade} de '{nome_produto}'.")
        else:
            resposta = "Produto não encontrado ou quantidade insuficiente."
            print(f"Compra falhou: Produto '{nome_produto}' não encontrado ou quantidade insuficiente.")
    cliente_socket.sendall(resposta.encode())

def gerenciar_conexao(cliente_socket, endereco, conexoes, produtos_marketplace, id_produtor):
    """
    Gerencia a comunicação com um cliente conectado. 
    Trata diferentes tipos de mensagens, como pedidos de compra e listagem de produtos, além de verificar o status de conexão com "heartbeat". 
    Imprime todas as mensagens recebidas e informações sobre o estado da conexão.
    """
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
                    produtos_marketplace.setdefault(endereco, []).append((nome_produto, quantidade))
                    comprar_produto_endpoint(cliente_socket, id_produtor, nome_produto, quantidade)
                elif data.startswith("LISTAR_PRODUTOS"):
                    listar_produtos_endpoint(cliente_socket, id_produtor)
                elif data.startswith("HEARTBEAT"):
                    cliente_socket.sendall("OK".encode('utf-8'))
    except Exception as e:
        print(f"Erro na conexão com {endereco}: {e}")
    finally:
        print(f"Conexão encerrada com {endereco}.")

def servidor_produtor(nome_produtor, id_produtor, porta, ip):
    """
    Inicia o servidor do produtor, permitindo que ele aceite conexões de clientes via sockets. 
    Inicia um thread para a atualização periódica do stock e trata as conexões dos clientes, lançando novos threads para cada cliente. 
    Imprime mensagens para monitorar o estado do servidor.
    """
    global servidor_ativo
    servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor_socket.bind(('', porta))
    servidor_socket.listen(5)
    print(f"Servidor do Produtor '{nome_produtor}' iniciado no IP {ip} e porta {porta}.")
    conexoes = []
    produtos_marketplace = {}
    threading.Thread(target=adicionar_stock_periodicamente, args=(id_produtor,)).start()
    while servidor_ativo:
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
    """
    Permite que um produtor existente inicie sessão. 
    Solicita o nome e ID do produtor, verifica se os dados estão corretos e, em caso de sucesso, retorna as informações do produtor. 
    Imprime uma mensagem de boas-vindas ou erro caso o produtor não seja encontrado.
    """
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

def menu_inicial():
    """
    Exibe o menu inicial do sistema, permitindo que o usuário crie um novo produtor ou inicie sessão com um produtor existente. 
    Dependendo da escolha, redireciona para a criação de um produtor ou para a sessão de um produtor já registrado. 
    Também oferece uma opção para sair do sistema.
    """
    while True:
        opcao = input("\n--- Menu Inicial ---\n1. Criar novo produtor\n2. Iniciar sessão com produtor existente\n99. Sair\nEscolha uma opção: ")
        if opcao == '1':
            nome_produtor = input("Digite o nome do novo produtor: ")
            id_produtor, porta, ip = registar_produtor(nome_produtor)
            gerar_itens_para_produtor(id_produtor, random.randint(3, 5))
            servidor_produtor(nome_produtor, id_produtor, porta, ip)
            break
        elif opcao == '2':
            nome_produtor, id_produtor, porta, ip = iniciar_sessao_produtor()
            if nome_produtor and id_produtor:
                servidor_produtor(nome_produtor, id_produtor, porta, ip)
            break
        elif opcao == '99':
            print("Saindo...")
            break

if __name__ == "__main__":
    menu_inicial()