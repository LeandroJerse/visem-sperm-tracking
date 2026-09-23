"""Fluxo completo e falhas da inspeção, usando somente entradas sintéticas."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from scripts.watershed import executar_inspecao as runner
from scripts.limiarizacao.inspecionar_imagem import ler_anotacoes, sha256
from analise import relatorio_inspecao_watershed as relatorio


class InspecaoWatershedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="watershed_sintetico_")
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.saida = self.raiz / "resultados/frame-to-frame/watershed/round0"
        self.plano = json.loads(runner.PLANO.read_text(encoding="utf-8"))
        self.dados = self.frozen()
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for mod in (runner, relatorio):
            self.stack.enter_context(patch.object(mod,"RAIZ",self.raiz))
            self.stack.enter_context(patch.object(mod,"SAIDA",self.saida))
        self.stack.enter_context(patch.object(runner,"congelar_entradas",return_value=self.dados))

    def frozen(self):
        entradas=[]
        im=np.zeros((96,128),np.uint8)
        im[10:24,12:28]=210;im[45:53,70:78]=230
        ok,png=cv2.imencode('.png',im);assert ok
        for q in self.plano['quadros']:
            blob=b'0 0.15625 0.177083333333 0.125 0.145833333333\n2 0.578125 0.510416666667 0.0625 0.083333333333\n'
            entradas.append({'quadro':q,'imagem_bytes':png.tobytes(),'anotacao_bytes':blob,'anotacoes':ler_anotacoes(blob)})
        return {'plano':self.plano,'plano_bytes':json.dumps(self.plano).encode(),
                'entradas':entradas,'hashes':{},'origens':{},'codigo':{'sintetico.txt':b'Teste sintetico'}}

    def rodar(self):
        with redirect_stdout(StringIO()):
            return runner.executar()

    def test_batch_sintetico_pdf_hashes_mapas_e_repeticao(self):
        pasta=self.rodar()
        d=relatorio.carregar(pasta)
        self.assertEqual(len(d['quadros']),48)
        self.assertEqual(len(d['resumos']),8)
        self.assertEqual(d['manifesto']['situacao'],'concluida')
        arquivos=list(pasta.rglob('mapas.npz'))
        self.assertEqual(len(arquivos),48)
        with np.load(arquivos[0],allow_pickle=False) as maps:
            np.testing.assert_array_equal(maps['regioes']>0,maps['mascara']>0)
        registro=json.loads((pasta/'relatorio.json').read_text(encoding='utf-8'))
        self.assertEqual(registro['situacao'],'concluido')
        pdf=self.raiz/registro['arquivo']
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
        nova=relatorio.gerar_relatorio(pasta)
        self.assertNotEqual(pdf,nova)
        for nome in ('resumo_configuracoes.csv','resumo_por_quadro.csv'):
            self.assertEqual(sha256((pasta/nome).read_bytes()),d['manifesto']['saidas_sha256'][(pasta/nome).relative_to(self.raiz).as_posix()])

    def test_recusa_saida_adulterada(self):
        pasta=self.rodar()
        (pasta/'resumo_configuracoes.csv').write_bytes(b'alterado')
        with self.assertRaises(ValueError):relatorio.carregar(pasta)

    def test_interrupcao_preserva_manifesto_e_nao_gera_pdf(self):
        with patch.object(runner,'executar_quadro',side_effect=RuntimeError('falha sintética')):
            with self.assertRaises(RuntimeError):self.rodar()
        pasta=next(self.saida.glob('batch__*'))
        m=json.loads((pasta/'execucao.json').read_text(encoding='utf-8'))
        self.assertEqual(m['situacao'],'falhou')
        self.assertEqual(m['avaliacoes_concluidas'],0)
        self.assertEqual(list(pasta.rglob('*.pdf')),[])
        with self.assertRaises(ValueError):relatorio.carregar(pasta)

    def test_falha_pdf_preserva_metricas_e_permite_recuperar(self):
        with patch.object(relatorio,'gerar_relatorio',side_effect=RuntimeError('PDF indisponível')):
            pasta=self.rodar()
        self.assertEqual(relatorio.carregar(pasta)['manifesto']['situacao'],'concluida')
        self.assertEqual(json.loads((pasta/'relatorio.json').read_text(encoding='utf-8'))['situacao'],'falhou')
        self.assertTrue(relatorio.gerar_relatorio(pasta).is_file())


if __name__=='__main__':unittest.main()
