from Vertice import Vertice
from Arista import Arista
from Grafo import Grafo
from Solucion import Solucion
from Tabu import Tabu
import random 
import sys
import re
import math 
import copy
import numpy as np
from clsTxt import clsTxt
from time import time

class CVRP:
    def __init__(self, M, D, nroV, capac, archivo, solI, opt, tADD, tDROP, tiempo, optimo):
        self._G = Grafo(M, D)       #Grafo original
        print(len(M))
        self.__S = Solucion(M, D, sum(D))    #Solucion general del CVRP
        self.__Distancias = M
        self.__Demandas = D         #Demandas de los clientes
        self.__capacidadMax = capac #Capacidad max por vehiculo
        self.__rutas = []           #Soluciones por vehiculo
        self.__costoTotal = 0
        self.__nroVehiculos = nroV
        self.__tipoSolucionIni = solI
        self.__beta = 1
        self.__optimosLocales = []

        self.__opt=opt
        self.__optimo = optimo
        self.__tenureADD =  tADD
        self.__tenureMaxADD = int(tADD*1.7)
        self.__tenureDROP =  tDROP
        self.__tenureMaxDROP = int(tDROP*1.7)
        self.__txt = clsTxt(str(archivo))
        self.__tiempoMaxEjec = float(tiempo)
        
        self.escribirDatos()
        self.__S.setCapacidadMax(self.__capacidadMax)
        self.__rutas = self.__S.rutasIniciales(self.__tipoSolucionIni, self.__nroVehiculos, self.__Demandas, self.__capacidadMax)
        self.__S = self.cargaSolucion(self.__rutas)

        print("\nSolucion general:" + str(self.__S))
        
        sol_ini = "\nRutas"
        for i in range(0, len(self.__rutas)):
            sol_ini+="Ruta #"+str(i+1)+": "+str(self.__rutas[i].getV())
            sol_ini+="\nCosto asociado: "+str(self.__rutas[i].getCostoAsociado())+"      Capacidad: "+str(self.__rutas[i].getCapacidad())+"\n"
        print(sol_ini)

        # print("\nAristas de la solucion: ")
        # for i in range(0, len(self.__S.getA())):
        #    print("arista %d: %s " %(i, str(self.__S.getA()[i])))
        #    print("id: ", self.__S.getA()[i].getId())

        # print("\nAristas del grafo: ")
        # for i in range(0, len(self._G.getA())):
        #    print("arista %d: %s " %(i, str(self._G.getA()[i])))
        #    print("id: ", self._G.getA()[i].getId())

        self.tabuSearch()

    #Escribe los datos iniciales: el grafo inicial y la demanda
    def escribirDatos(self):
        self.__txt.escribir("+-+-+-+-+-+-+-+-+-+-+-+-+-+-+ GRAFO CARGADO +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-")
        self.__txt.escribir(str(self._G))
        cad = "\nDemandas:"
        print(cad)
        for v in self._G.getV():
            cad_aux = str(v)+": "+str(v.getDemanda())
            print(cad_aux) 
            cad+="\n"+ cad_aux
        self.__txt.escribir(cad)
        print("SumDemanda: ",sum(self.__Demandas))
        print("Nro vehiculos: ",self.__nroVehiculos)
        self.__txt.escribir("+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+ SOLUCION INICIAL +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-")

    #Carga la solucion general a partir de las rutas
    def cargaSolucion(self, rutas):
        A = []
        V = []
        S = Solucion(self.__Distancias, self.__Demandas, sum(self.__Demandas))
        cap = 0
        costoTotal = 0
        sol_ini = ""
        
        for i in range(0, len(rutas)):
            try:
                s = rutas[i]
            except ValueError:
                print("i: "+str(i))
                print("rutas: "+str(s))
            costoTotal += s.getCostoAsociado()
            cap += s.getCapacidad()
            A.extend(s.getA())
            V.extend(s.getV())
            sol_ini+="\nRuta #"+str(i+1)+": "+str(self.__rutas[i].getV())
            sol_ini+="\nCosto asociado: "+str(self.__rutas[i].getCostoAsociado())+"      Capacidad: "+str(self.__rutas[i].getCapacidad())+"\n"
        sol_ini+="\n--> Costo total: "+str(costoTotal)+"          Capacidad total: "+str(cap)
        #print(sol_ini)
        self.__txt.escribir(sol_ini)
        S.setA(A)
        S.setV(V)
        S.setCostoAsociado(costoTotal)
        S.setCapacidad(cap)
        S.setCapacidadMax(self.__capacidadMax)
        
        return S

    #Umbral de granularidad: phi = Beta*(c/(n+k))
    #Beta = 1  parametro de dispersion. Sirve para modificar el grafo disperso para incluir la diversificación y la intensificación
    #          durante la búsqueda.
    #c = valor de una sol. inicial
    #k = nro de vehiculos
    #n = nro de clientes
    def calculaUmbral(self, costo):
        c = costo
        k = self.__nroVehiculos
        n = len(self.__Distancias)-1
        phi = c/(n+k)
        phi = phi*self.__beta
        return round(phi,3)

    #+-+-+-+-+-+-+- Empezamos con Tabu Search +-+-+-+-+-+-+-+-+#
    #lista_tabu: tiene objetos de la clase Tabu (una arista con su tenure)
    #Lista_permitidos: o grafo disperso tiene elementos del tipo Arista que no estan en la lista tabu y su distancia es menor al umbral
    #nuevas_rutas: nuevas rutas obtenidas a partir de los intercambios
    #nueva_solucion: nueva solucion obtenida a partir de los intercambios
    #rutas_refer: rutas de referencia que sirve principalmente para evitar estancamiento, admitiendo una solucion peor y hacer los intercambios
    #             a partir de esas
    #solucion_refer: idem al anterior
    #umbral: valor de umbral de granularidad
    #tiempoIni: tiempo inicial de ejecucion - tiempoMax: tiempo maximo de ejecucion - tiempoEjecuc: tiempo de ejecución actual
    #iteracEstancamiento: iteraciones de estancamiento para admitir una solución peor, modificar Beta y escapar del estancamiento
    #iterac: cantidad de iteraciones actualmente
    def tabuSearch(self):
        lista_tabu = []
        ind_permitidos = np.array([], dtype = int)
        nuevas_rutas = copy.deepcopy(self.__rutas)
        rutas_refer = copy.deepcopy(nuevas_rutas)
        nueva_solucion = copy.deepcopy(self.__S)
        solucion_refer = copy.deepcopy(nueva_solucion)
        nuevo_costo = self.__S.getCostoAsociado()
        
        #Atributos de tiempo e iteraciones
        tiempoIni = time()
        tiempoMax = float(self.__tiempoMaxEjec*60)
        tiempoEstancamiento = tiempoIni
        tiempoEjecuc = 0
        iteracEstancamiento = 1
        iteracEstancamiento_Opt = 1
        iterac = 1
        umbral = self.calculaUmbral(self.__S.getCostoAsociado())

        porc_Estancamiento = 1.05
        porc_EstancamientoMax = 1.2

        cond_2opt = True
        cond_3opt = True
        cond_Optimiz = True

        Aristas_Opt = np.array([], dtype = object)
        for EP in self._G.getA():
            if(EP.getOrigen() != EP.getDestino() and EP.getDestino()!=1 and EP.getPeso() <= umbral):
                Aristas_Opt = np.append(Aristas_Opt, EP)
                ind_permitidos = np.append(ind_permitidos, EP.getId())
        ind_permitidos = np.unique(ind_permitidos)
        Aristas = Aristas_Opt
        # print("\nInd Aristas: "+str(ind_permitidos))
        # for i in ind_permitidos:
        #     print("Arista %d: %s" %(i, str(self._G.getA()[i])))

        print("Aplicamos 2-opt")
        porcentaje = round(self.__S.getCostoAsociado()/self.__optimo -1.0, 3)
        while(tiempoEjecuc < tiempoMax or porcentaje*100<5):
            if(cond_Optimiz):
                ind_permitidos, Aristas = self.getPermitidos(Aristas, lista_tabu, umbral, cond_Optimiz, solucion_refer)    #Lista de elementos que no son tabu
                ind_AristasOpt = copy.deepcopy(ind_permitidos)
            cond_Optimiz = False
            ADD = []
            DROP = []
            
            #ind_random = [x for x in range(0,len(lista_permitidos))]
            ind_random = np.arange(0,len(ind_permitidos))
            random.shuffle(ind_random)
            
            if(iteracEstancamiento_Opt>50):
                iteracEstancamiento_Opt = 1
                if(cond_2opt):
                    print("Aplicamos 3-opt")
                    cond_2opt = False
                elif(cond_3opt):
                    print("Aplicamos 4-opt")
                    cond_3opt = False
                else:
                    print("Aplicamos 2-opt")
                    cond_2opt = cond_3opt = True

            if(cond_2opt):
                nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_2opt(self._G.getA(), ind_permitidos, ind_random, rutas_refer)
                #nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_2opt(lista_permitidos, ind_random, rutas_refer)
            #Para aplicar, cada ruta tiene que tener al menos 3 clientes (o 4 aristas)
            elif(cond_3opt):
            #    nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_3opt(lista_permitidos, ind_random, rutas_refer)
                nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_3opt(self._G.getA(), ind_permitidos, ind_random, rutas_refer)
            #Para aplicar, cada ruta tiene que tener al menos 3 clientes (o 4 aristas)
            else:
            #    nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_4opt(lista_permitidos, ind_random, rutas_refer)
                nuevas_rutas, aristas_ADD, aristas_DROP, nuevo_costo = nueva_solucion.swap_4opt(self._G.getA(), ind_permitidos, ind_random, rutas_refer)
            #print("time swap: "+str(time()-timeSwap))
            
            tenureADD = self.__tenureADD
            tenureDROP = self.__tenureDROP
            
            costo_sol = self.__S.getCostoAsociado()
            #Si encontramos una mejor solucion que la tomada como referencia
            if(nuevo_costo < solucion_refer.getCostoAsociado()):
                cad = "\n+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+- Iteracion %d  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-\n" %(iterac)
                self.__txt.escribir(cad)
                nueva_solucion = self.cargaSolucion(nuevas_rutas)
                solucion_refer = nueva_solucion
                rutas_refer = nuevas_rutas
                #Si la nueva solucion es mejor que la obtenida hasta el momento
                if(nueva_solucion.getCostoAsociado() < self.__S.getCostoAsociado()):
                    tiempoTotal = time()-tiempoEstancamiento
                    cad += "\nLa solución anterior duró " + str(int(tiempoTotal/60))+"min "+ str(int(tiempoTotal%60))
                    cad += "seg    -------> Nuevo optimo local. Costo: "+str(nueva_solucion.getCostoAsociado())
                    print(cad)
                    self.__S = nueva_solucion
                    self.__rutas = nuevas_rutas
                    tiempoEstancamiento = time()
                    self.__beta = 1
                else:
                    cad += "\nNuevo optimo. Costo: "+str(nueva_solucion.getCostoAsociado())
                    print(cad)
                cad += "\nLista tabu: "+str(lista_tabu)
                self.__txt.escribir(cad)
                umbral = self.calculaUmbral(nueva_solucion.getCostoAsociado())
                tenureADD = self.__tenureMaxADD
                tenureDROP = self.__tenureMaxDROP
                cond_Optimiz = True
                Aristas = Aristas_Opt
                iteracEstancamiento = 1
                iteracEstancamiento_Opt = 1
                porc_Estancamiento = 1.05
                porc_EstancamientoMax = 1.2
            #Si se estancó, tomamos la proxima solución peor que difiera un 5% del optimo como referencia
            elif(nuevo_costo < costo_sol*porc_EstancamientoMax and nuevo_costo > costo_sol*porc_Estancamiento and iteracEstancamiento>100):
                nueva_solucion = self.cargaSolucion(nuevas_rutas)
                tiempoTotal = time()-tiempoEstancamiento
                print("Se estancó durante %d min %d seg. Admitimos una solucion peor para diversificar" %(int(tiempoTotal/60), int(tiempoTotal%60)))
                if(porc_EstancamientoMax < 1.3):
                    porc_Estancamiento += 0.02
                    porc_EstancamientoMax += 0.02
                else:
                    print("reiniciamos la lista tabu")
                    porc_Estancamiento = 1.05
                    porc_EstancamientoMax = 1.2
                lista_tabu = []
                ind_permitidos = ind_AristasOpt
                self.__beta = 2
                umbral = self.calculaUmbral(nueva_solucion.getCostoAsociado())
                solucion_refer = nueva_solucion
                rutas_refer = nuevas_rutas
                cond_Optimiz = True
                iteracEstancamiento = 1
                Aristas = Aristas_Opt
            elif(iteracEstancamiento>100):
                porc_Estancamiento = 1.05
                porc_EstancamientoMax = 1.2
            else:
                nuevas_rutas = rutas_refer
                nueva_solucion = solucion_refer
            
            if (aristas_ADD != []):
                ADD.append(Tabu(aristas_ADD[0], tenureADD))
                for i in range(0, len(aristas_DROP)):
                    DROP.append(Tabu(aristas_DROP[i], tenureDROP))
                self.decrementaTenure(lista_tabu, ind_permitidos)
                lista_tabu.extend(DROP)
                lista_tabu.extend(ADD)
            else:
                lista_tabu = []
                ind_permitidos = ind_AristasOpt
                porc_Estancamiento = 1.05
                porc_EstancamientoMax = 1.2
            
            #print(time()-tiempoEjecuc)
            tiempoEjecuc = time()-tiempoIni
            iterac += 1
            iteracEstancamiento += 1
            iteracEstancamiento_Opt += 1
        #Fin del while. Imprimo los valores obtenidos

        print("\nMejor solucion obtenida: "+str(self.__rutas))
        tiempoTotal = time() - tiempoIni
        print("\nTermino!! :)")
        print("Tiempo total: " + str(int(tiempoTotal/60))+"min "+str(int(tiempoTotal%60))+"seg\n")
        self.__txt.escribir("\n+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+- Solucion Optima +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-")
        sol_ini = ""
        for i in range(0, len(self.__rutas)):
            sol_ini+="\nRuta #"+str(i+1)+": "+str(self.__rutas[i].getV())
            sol_ini+="\nCosto asociado: "+str(self.__rutas[i].getCostoAsociado())+"      Capacidad: "+str(self.__rutas[i].getCapacidad())+"\n"
        self.__txt.escribir(sol_ini)
        porcentaje = round(self.__S.getCostoAsociado()/self.__optimo -1.0, 3)
        self.__txt.escribir("\nCosto total:  " + str(self.__S.getCostoAsociado()) + "        Optimo real:  " + str(self.__optimo)+
                            "      Desviación: "+str(porcentaje*100)+"%")
        self.__txt.escribir("\nCantidad de iteraciones: "+str(iterac))
        self.__txt.escribir("Nro de vehiculos: "+str(self.__nroVehiculos))
        self.__txt.escribir("Capacidad Maxima/Vehiculo: "+str(self.__capacidadMax))
        self.__txt.escribir("Tiempo total: " + str(int(tiempoTotal/60))+"min "+str(int(tiempoTotal%60))+"seg")
        tiempoTotal = time()-tiempoEstancamiento
        self.__txt.escribir("Tiempo de estancamiento: "+str(int(tiempoTotal/60))+"min "+str(int(tiempoTotal%60))+"seg")
        self.__txt.imprimir()


    def getPermitidos(self, Aristas, lista_tabu, umbral, cond_Optimiz, solucion):
        #ListaPermit = []           #Aristas permitidas de todas las aristas del grafo original
        AristasNuevas = []
        ind_permitidos = np.array([], dtype = int)

        #No tengo en consideracion a las aristas que exceden el umbral y las que pertencen a S
        # if(cond_Optimiz):
        for EP in Aristas:
            pertS = False
            for A_S in solucion.getA():
                if A_S == EP:
                    pertS = True
                    break
            if(not pertS and EP.getPeso() <= umbral):
                AristasNuevas.append(EP)
                ind_permitidos = np.append(ind_permitidos, EP.getId())
        # else:
        #     AristasNuevas = Aristas
        ind_permitidos = np.unique(ind_permitidos)

        #La lista tabu esta vacia, entonces la lista de permitidas tiene todas las aristas anteriores
        #if(len(lista_tabu) == 0):
        #    print("len: "+str(len(lista_tabu)))
        #     ListaPermit = AristasNuevas
        #     print("aristas_nuevas: "+str(AristasNuevas))
        # #La lista tabu tiene elementos, agrego los que no estan en lista tabu
        # else:
        #     for i in range(0, len(AristasNuevas)):
        #         EP = AristasNuevas[i]
        #         cond = True
        #         j = 0
        #         while(j < len(lista_tabu) and cond):
        #             ET = lista_tabu[j] 
        #             if(EP == ET.getElemento()):
        #                 cond = False
        #             j+=1
        #         if(cond):
        #             ListaPermit.append(EP)
            
        #return ListaPermit, AristasNuevas
        return ind_permitidos, AristasNuevas

    #Decrementa el Tenure en caso de que no sea igual a -1. Si luego de decrementar es 0, lo elimino de la lista tabu
    def decrementaTenure(self, lista_tabu, ind_permitidos):
        i=0
        while (i < len(lista_tabu)):
            elemTabu=lista_tabu[i]
            elemTabu.decrementaT()
            if(elemTabu.getTenure()==0):
                ind_permitidos = np.append(ind_permitidos, elemTabu.getElemento().getId())
                lista_tabu.pop(i)
                i-=1
            i+=1
    