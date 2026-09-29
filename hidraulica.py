import math
G=9.81

def area_circular(D): return math.pi*float(D)**2/4.0
def velocidad(Q,D): return float(Q)/area_circular(D)
def carga_velocidad(V,g=G): return float(V)**2/(2*g)
def reynolds(V,D,nu): return abs(float(V))*float(D)/float(nu)
def factor_friccion(Re, eps_rel):
    Re=float(Re); eps_rel=float(eps_rel)
    if Re<=0: raise ValueError('Re inválido')
    if Re<2300: return 64.0/Re
    # Colebrook
    f=0.02
    for _ in range(100):
        nf=1.0/(-2.0*math.log10(eps_rel/3.7 + 2.51/(Re*math.sqrt(f))))**2
        if abs(nf-f)<1e-13: return nf
        f=nf
    return f

def calcular_sistema_para_q(Q,tramos,nu,g=G):
    resultados=[]; thf=0.; thm=0.
    for t in tramos:
        D=float(t['D']); L=float(t['L']); eps=float(t.get('epsilon',0)); K=float(t.get('K',0) or 0)
        A=area_circular(D); V=float(Q)/A; Re=reynolds(V,D,nu); er=eps/D; f=factor_friccion(Re,er)
        vh=V*V/(2*g); hf=f*(L/D)*vh; hm=K*vh
        resultados.append({'Tramo':t.get('numero',len(resultados)+1),'L (m)':L,'D (m)':D,'epsilon (m)':eps,'A (m2)':A,'V (m/s)':V,'Re':Re,'f Darcy':f,'K':K,'hf (m)':hf,'hm (m)':hm,'regimen':'Laminar' if Re<2300 else ('Transición' if Re<4000 else 'Turbulento')})
        thf+=hf; thm+=hm
    return {'resultados':resultados,'total_hf':thf,'total_hm':thm,'hL_total':thf+thm}

def calcular_para_diametro(D,Q,L,epsilon,nu,K=0.0,g=G):
    A=area_circular(D); V=Q/A; Re=reynolds(V,D,nu); er=epsilon/D; f=factor_friccion(Re,er); vh=V*V/(2*g); hf=f*(L/D)*vh; hm=K*vh
    return {'D':D,'A':A,'V':V,'Re':Re,'regimen':'Laminar' if Re<2300 else ('Transición' if Re<4000 else 'Turbulento'),'eps_rel':er,'f':f,'hf':hf,'hm':hm,'hL':hf+hm}

def buscar_diametro_clase_iii_a(Q,L,epsilon,nu,hL_permitida,D_min=0.005,D_max=2.0,g=G):
    def r(d): return calcular_para_diametro(d,Q,L,epsilon,nu,0,g)['hf']-hL_permitida
    a,b=D_min,D_max; fa,fb=r(a),r(b)
    if fa*fb>0: raise ValueError('sin bracket')
    for i in range(100):
        c=(a+b)/2; fc=r(c)
        if abs(fc)<1e-10: break
        if fa*fc<=0: b,fb=c,fc
        else: a,fa=c,fc
    e=calcular_para_diametro(c,Q,L,epsilon,nu,0,g)
    return {**e,'D_minimo':c,'residual':fc,'iteraciones':i+1,'convergencia':abs(fc)<1e-7}

def peso_especifico(rho,g=G): return float(rho)*g

def residuo_energia(P1,P2,z1,z2,V1,V2,hA,hR,hL,gamma,g=G):
    return float(P1)/gamma+z1+V1**2/(2*g)+(hA or 0)-float(P2)/gamma-z2-V2**2/(2*g)-(hR or 0)-hL

def resolver_clase_i(incognita,P1,P2,z1,z2,V1,V2,hA,hR,hL,gamma,g=G):
    # H1 + hA - hR - hL = H2
    if incognita=='hA':
        return P2/gamma+z2+V2**2/(2*g)+(hR or 0)+hL - (P1/gamma+z1+V1**2/(2*g))
    if incognita=='hR':
        return P1/gamma+z1+V1**2/(2*g)+(hA or 0)-hL-(P2/gamma+z2+V2**2/(2*g))
    if incognita=='P2':
        return gamma*(P1/gamma+z1+V1**2/(2*g)+(hA or 0)-(hR or 0)-hL-z2-V2**2/(2*g))
    if incognita=='P1':
        return gamma*(P2/gamma+z2+V2**2/(2*g)+(hR or 0)+hL-(hA or 0)-z1-V1**2/(2*g))
    if incognita=='z2':
        return P1/gamma+z1+V1**2/(2*g)+(hA or 0)-(hR or 0)-hL-P2/gamma-V2**2/(2*g)
    if incognita=='z1':
        return P2/gamma+z2+V2**2/(2*g)+(hR or 0)+hL-(hA or 0)-P1/gamma-V1**2/(2*g)
    raise ValueError(incognita)

def potencia_hidraulica_bomba(gamma,Q,hA): return gamma*Q*hA
def potencia_entrada_bomba(gamma,Q,hA,eficiencia): return gamma*Q*hA/eficiencia

def verificar_clase_iii_b(D_actual,Q,L,epsilon,nu,K,gamma,P1,P2_deseada,z1,z2,hA,hR,tipo_v1,tipo_v2,V1_manual=0.0,V2_manual=0.0,g=G):
    e=calcular_para_diametro(D_actual,Q,L,epsilon,nu,K,g)
    def vext(tipo, manual):
        if tipo=='deposito': return 0.0
        if tipo=='manual': return manual
        return e['V']
    V1=vext(tipo_v1,V1_manual); V2=vext(tipo_v2,V2_manual)
    # E1+hA-hR-hL = E2
    P2=gamma*(P1/gamma+z1+V1**2/(2*g)+hA-hR-e['hL']-z2-V2**2/(2*g))
    return {**e,'P2_calculada':P2,'P2_deseada':P2_deseada,'margen_presion':P2-P2_deseada,'cumple':P2>=P2_deseada}


# Compatibilidad de interfaz: carga disponible para Clase III-A.
def carga_disponible_clase_iii_a(P1,P2,z1,z2,hA,hR,gamma):
    if gamma is None or float(gamma) <= 0:
        raise ValueError("gamma debe ser mayor que cero")
    hL = float(P1)/float(gamma) + float(z1) + float(hA or 0.0) - float(hR or 0.0) - float(P2)/float(gamma) - float(z2)
    if hL <= 0:
        raise ValueError("La carga disponible para pérdidas debe ser positiva.")
    return hL
