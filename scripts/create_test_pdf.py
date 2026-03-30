"""Gera um PDF de NF-e fake para teste (sem dependências externas)."""
import sys
from pathlib import Path

def create_nfe_pdf(output_path: str):
    # PDF mínimo com texto embutido (sem biblioteca externa)
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 800>>
stream
BT
/F1 12 Tf
50 750 Td (NOTA FISCAL ELETRONICA - NF-e) Tj
0 -20 Td (DANFE - Documento Auxiliar da Nota Fiscal Eletronica) Tj
0 -20 Td (CHAVE DE ACESSO: 3526031234567800019955001000123456) Tj
0 -40 Td (EMITENTE) Tj
0 -20 Td (Razao Social: Empresa Teste Ltda) Tj
0 -20 Td (CNPJ: 12.345.678/0001-99) Tj
0 -40 Td (DESTINATARIO) Tj
0 -20 Td (Razao Social: Cliente Teste SA) Tj
0 -20 Td (CNPJ DESTINATARIO: 98.765.432/0001-10) Tj
0 -40 Td (NUMERO: 000123456) Tj
0 -20 Td (DATA DE EMISSAO: 15/03/2026) Tj
0 -40 Td (Valor Total da Nota: R$ 1.250,00) Tj
ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000001118 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
1200
%%EOF"""

    Path(output_path).write_bytes(content)
    print(f"✓ PDF criado: {output_path}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/nfe_teste.pdf"
    create_nfe_pdf(out)
