# Receita registrada — Raspberry EnergyCube, 10/11/2026

O proprietário confirmou o acesso remoto funcionando após os ajustes abaixo.
A causa final do 502 não foi isolada: ativar um arquivo de diagnóstico não é,
por si só, uma correção de transporte. Esta receita registra a configuração
observada, sem atribuir a recuperação a uma mudança não comprovada.

## Configuração da instalação analisada

- Raspberry Pi OS ARM64; D-Max local em HTTP/80, gateway em 127.0.0.1:8766.
- Wi-Fi gerenciado pelo NetworkManager, com dois IPs existentes preservados.
- O DNS recebido do gateway expirou no teste. Dois servidores DNS internos e um
  DNS público responderam. Foram usados os dois internos validados, com
  `ipv4.ignore-auto-dns yes`, aplicados com `nmcli device reapply wlan0`.
  Nome da conexão e endereços específicos foram guardados na receita local do
  proprietário. Em outro cliente, teste e use os servidores autorizados dessa rede.
- cloudflared oficial 2026.10.7, supervisor corrigido da 0.12.1, protocolo auto,
  IPv4, fallback nativo QUIC/HTTP2, verificação TLS mantida.
- `/ready` em 127.0.0.1:20246 confirmou uma conexão registrada. Acesso ao gateway
  como usuário dmax-remote retornou HTTP 200 com Host público e protocolo HTTPS.
- Pré-testes indicaram alcance parcial: region1 respondeu e region2 falhou.
  Essa observação não prova isoladamente uma regra de firewall.
- D-Max, usuários, banco, recargas e Grafana permaneceram separados do túnel.

## Registro temporário usado na investigação

```sh
sudo mkdir -p /run/systemd/system/d-max-remote.service.d
printf '[Service]\nEnvironment="TUNNEL_LOGFILE=/var/lib/d-max-remote/cloudflared-diagnostico.log"\n' | sudo tee /run/systemd/system/d-max-remote.service.d/90-diagnostico.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart d-max-remote
sudo bash /opt/d-max/acesso-remoto.sh status
sudo tail -n 80 /var/lib/d-max-remote/cloudflared-diagnostico.log
```

Esse override fica em /run e desaparece após reiniciar o Raspberry. Não é uma
exigência para operar o túnel. Enquanto estiver habilitado, acompanhe o tamanho
do arquivo de diagnóstico. Para encerrar a coleta, remova somente esse override
com `sudo rm /run/systemd/system/d-max-remote.service.d/90-diagnostico.conf`, execute
`sudo systemctl daemon-reload` e reinicie somente d-max-remote. A URL pode mudar.
Não faça essa limpeza no meio de uma supervisão em uso.

## Verificação para outras instalações

1. Confirmar tela local, depois gateway por loopback com Host público e HTTPS.
2. Conferir DNS e conectividade aos destinos Cloudflare na porta 7844 (QUIC/UDP
   ou HTTP2/TCP, conforme a política autorizada da rede).
3. Conferir prontidão do conector e abrir o endereço atual em uma rede externa.
4. Confirmar login e atualização da URL na planilha; não usar URLs antigas nem
   api.trycloudflare.com como endereço de acesso.
5. Se houver falha, coletar a mensagem original com log em nível info. Não
   desabilitar TLS, abrir OCPP ao público ou alterar IP/DNS sem testar a causa.

## Preservação na 0.13.0

O supervisor da 0.12.1 e o cliente oficial foram mantidos sem mudanças. A nova
versão não altera DNS, IPs, gateway da rede nem o override de diagnóstico existente.
