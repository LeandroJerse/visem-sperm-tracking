"""Contratos geométricos e compatibilidade do watershed, apenas com imagens sintéticas."""

from dataclasses import asdict, replace
import unittest

import cv2
import numpy as np

from algoritmos.classicos.classificacao import ConfiguracaoArea
from algoritmos.classicos.comum import ClasseObjeto
from algoritmos.classicos.limiarizacao import ConfiguracaoLimiarizacao, ConfiguracaoMorfologia
from algoritmos.classicos.watershed import ConfiguracaoWatershed, configuracao_de_dict, detectar, inspecionar
from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import avaliar
from scripts.blobs.executar_inspecao import objetos
from scripts.limiarizacao.inspecionar_imagem import ler_anotacoes


def config(**alteracoes):
    m = ConfiguracaoMorfologia("elipse", 3, 0)
    s = ConfiguracaoLimiarizacao("manual", "claro", 127, m, m, 8, 1, None, ConfiguracaoArea(10, 250))
    return replace(ConfiguracaoWatershed(s, .75, "separar"), **alteracoes)


class WatershedTest(unittest.TestCase):
    def test_caixa_yolo_area_centroide_e_iou_da_regiao(self):
        im = np.zeros((30, 40), np.uint8); im[5:12, 8:18] = 200
        r = detectar(im, config()); d = r.deteccoes[0]
        self.assertEqual((d.caixa.x,d.caixa.y,d.caixa.largura,d.caixa.altura), (8,5,10,7))
        self.assertEqual((d.medidas.area_pixels,d.medidas.centroide_x,d.medidas.centroide_y), (70,12.5,8.0))
        self.assertEqual(d.medidas.intensidade_media, 200)
        yolo = ler_anotacoes((r.linhas_yolo()[0]+'\n').encode())[0]
        self.assertAlmostEqual(yolo['caixa_centro_x_norm'],13/40)
        a = avaliar([Objeto(0,0,8,5,10,7)], objetos(list(r.registros()),'indice_deteccao'))
        self.assertEqual(a['por_grupo']['individuos']['f1'],1)

    def test_dois_circulos_tocando_separam_sem_perder_pixels(self):
        im = np.zeros((60, 90), np.uint8)
        cv2.circle(im,(30,30),14,255,-1); cv2.circle(im,(53,30),14,255,-1)
        d = inspecionar(im,config())
        self.assertEqual(len(d.componentes_info),1)
        self.assertEqual(len(d.resultado.deteccoes),2)
        np.testing.assert_array_equal(d.regioes>0,im>0)
        self.assertEqual(sum(x['area_pixels'] for x in d.candidatos),int((im>0).sum()))

    def test_preservar_aglomerado_emite_pai_sem_filhos(self):
        im = np.zeros((60,90),np.uint8)
        cv2.circle(im,(30,30),14,255,-1);cv2.circle(im,(53,30),14,255,-1)
        d = inspecionar(im,config(politica_aglomerados='preservar_por_area'))
        self.assertEqual(len(d.resultado.deteccoes),1)
        self.assertEqual(d.resultado.deteccoes[0].classe,ClasseObjeto.AGLOMERADO)
        self.assertEqual(d.resultado.deteccoes[0].medidas.area_pixels,int((im>0).sum()))
        self.assertEqual(d.componentes_info[0]['sementes'],2)

    def test_semente_local_nao_elimina_componente_pequeno(self):
        im = np.zeros((90,90),np.uint8)
        cv2.circle(im,(30,30),22,255,-1); im[75,75]=255
        d=inspecionar(im,config(fracao_semente=1))
        self.assertEqual(len(d.resultado.deteccoes),2)
        self.assertEqual(d.resultado.deteccoes[-1].medidas.area_pixels,1)

    def test_bordas_e_imagem_inteira(self):
        for shape in ((1,1),(1,9),(9,1),(8,12)):
            with self.subTest(shape=shape):
                im=np.full(shape,255,np.uint8)
                d=inspecionar(im,config())
                self.assertEqual(sum(x['area_pixels'] for x in d.candidatos),im.size)
                for det in d.resultado.deteccoes:det.caixa.normalizada(shape[1],shape[0])

    def test_vazio_e_polaridade_invertida(self):
        im=np.zeros((20,30),np.uint8)
        self.assertEqual(detectar(im,config()).deteccoes,())
        c=config();c=replace(c,segmentacao=replace(c.segmentacao,polaridade='escuro'))
        im[3:9,4:11]=255
        np.testing.assert_array_equal(inspecionar(255-im,c).mascara,inspecionar(im,config()).mascara)

    def test_filtro_area_e_diagnostico_rejeitado(self):
        im=np.zeros((20,30),np.uint8);im[1:3,1:3]=255;im[6:10,7:12]=255
        c=config();c=replace(c,segmentacao=replace(c.segmentacao,area_minima=5,area_maxima=20))
        d=inspecionar(im,c)
        self.assertEqual(len(d.resultado.deteccoes),1)
        self.assertEqual(d.candidatos[0]['situacao'],'area_abaixo_minimo')
        self.assertEqual(d.resultado.deteccoes[0].medidas.area_pixels,20)

    def test_conectividade_consistente(self):
        im=np.zeros((8,8),np.uint8);im[3,3]=im[4,4]=255
        c=config()
        self.assertEqual(len(inspecionar(im,c).componentes_info),1)
        c=replace(c,segmentacao=replace(c.segmentacao,conectividade=4))
        self.assertEqual(len(inspecionar(im,c).componentes_info),2)

    def test_imagem_preservada_bgr_e_repetibilidade(self):
        im=np.zeros((25,30),np.uint8);im[4:12,5:14]=170
        original=im.copy()
        a=inspecionar(im,config());b=inspecionar(cv2.cvtColor(im,cv2.COLOR_GRAY2BGR),config())
        np.testing.assert_array_equal(im,original)
        self.assertEqual(a.resultado,b.resultado)
        np.testing.assert_array_equal(a.regioes,b.regioes)

    def test_classes_por_area_com_limites_inclusivos(self):
        for area,classe in ((10,2),(11,0),(249,0),(250,1)):
            im=np.full((1,area),255,np.uint8)
            self.assertEqual(int(detectar(im,config()).deteccoes[0].classe),classe)

    def test_configuracoes_invalidas_e_parser_estrito(self):
        for f in (0,-1,1.1,float('nan'),True):
            with self.assertRaises((TypeError,ValueError)):config(fracao_semente=f)
        with self.assertRaises(ValueError):config(politica_aglomerados='ignorar')
        p=asdict(config());self.assertEqual(configuracao_de_dict(p),config())
        p['desconhecido']=1
        with self.assertRaises(ValueError):configuracao_de_dict(p)
        with self.assertRaises(ValueError):detectar(np.zeros((3,3),np.float32),config())


if __name__=='__main__': unittest.main()
