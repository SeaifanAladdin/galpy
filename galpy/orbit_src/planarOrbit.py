import math as m
import numpy as nu
from scipy import integrate
import galpy.util.bovy_plot as plot
from OrbitTop import OrbitTop
from RZOrbit import RZOrbit
from galpy.potential_src.planarPotential import evaluateplanarRforces,\
    planarPotential, RZToplanarPotential, evaluateplanarphiforces,\
    evaluateplanarPotentials
from galpy.potential_src.Potential import Potential
class planarOrbitTop(OrbitTop):
    """Top-level class representing a planar orbit (i.e., one in the plane 
    of a galaxy)"""
    def __init__(self,vxvv=None):
        """
        NAME:
           __init__
        PURPOSE:
           Initialize a planar orbit
        INPUT:
           vxvv - [R,vR,vT(,phi)]
        OUTPUT:
        HISTORY:
           2010-07-12 - Written - Bovy (NYU)
        """
        return None

    def e(self):
        """
        NAME:
           e
        PURPOSE:
           calculate the eccentricity
        INPUT:
        OUTPUT:
           eccentricity
        HISTORY:
           2010-09-15 - Written - Bovy (NYU)
        """
        if not hasattr(self,'orbit'):
            raise AttributeError("Integrate the orbit first")
        if not hasattr(self,'rs'):
            self.rs= self.orbit[:,0]**2.
        return (nu.amax(self.rs)-nu.amin(self.rs))/(nu.amax(self.rs)+nu.amin(self.rs))

    def rap(self):
        """
        NAME:
           rap
        PURPOSE:
           return the apocenter radius
        INPUT:
        OUTPUT:
           R_ap
        HISTORY:
           2010-09-20 - Written - Bovy (NYU)
        """
        if not hasattr(self,'orbit'):
            raise AttributeError("Integrate the orbit first")
        if not hasattr(self,'rs'):
            self.rs= self.orbit[:,0]**2.
        return nu.amax(self.rs)

    def rperi(self):
        """
        NAME:
           rperi
        PURPOSE:
           return the pericenter radius
        INPUT:
        OUTPUT:
           R_peri
        HISTORY:
           2010-09-20 - Written - Bovy (NYU)
        """
        if not hasattr(self,'orbit'):
            raise AttributeError("Integrate the orbit first")
        if not hasattr(self,'rs'):
            self.rs= self.orbit[:,0]**2.
        return nu.amin(self.rs)

    def zmax(self):
        raise AttributeError("planarOrbit does not have a zmax")

class planarROrbit(planarOrbitTop):
    """Class representing a planar orbit, without \phi. Useful for 
    orbit-integration in axisymmetric potentials when you don't care about the
    azimuth"""
    def __init__(self,vxvv=[1.,0.,1.]):
        """
        NAME:
           __init__
        PURPOSE:
           Initialize a planarROrbit
        INPUT:
           vxvv - [R,vR,vT]
        OUTPUT:
        HISTORY:
           2010-07-12 - Written - Bovy (NYU)
        """
        self.vxvv= vxvv
        return None

    def integrate(self,t,pot):
        """
        NAME:
           integrate
        PURPOSE:
           integrate the orbit
        INPUT:
           t - list of times at which to output (0 has to be in this!)
           pot - potential instance or list of instances
        OUTPUT:
           (none) (get the actual orbit using getOrbit()
        HISTORY:
           2010-07-20
        """
        thispot= RZToplanarPotential(pot)
        self.t= nu.array(t)
        self.orbit= _integrateROrbit(self.vxvv,thispot,t)

    def plot(self,*args,**kwargs):
        """
        NAME:
           plot
        PURPOSE:
           plot a planar Orbit
        INPUT:
           bovy_plot args and kwargs
        OUTPUT:
           plot
        HISTORY:
           2010-07-26 - Written - Bovy (NYU)
        """
        if not kwargs.has_key('xlabel'):
            kwargs['xlabel']= r'$R$'
        if not kwargs.has_key('ylabel'):
            kwargs['ylabel']= r'$v_R$'
        plot.bovy_plot(self.orbit[:,0],
                       self.orbit[:,1],*args,**kwargs)

    def plotEt(self,pot,*args,**kwargs):
        """
        NAME:
           plotEt
        PURPOSE:
           plot E(t) along the orbit
        INPUT:
           pot - Potential instance or list of instances in which the orbit was
                 integrated
           +bovy_plot.bovy_plot inputs
        OUTPUT:
           figure to output device
        HISTORY:
           2010-07-10 - Written - Bovy (NYU)
        """
        self.E= [evaluateplanarPotentials(self.orbit[ii,0],pot)+
                 self.orbit[ii,1]**2./2.+self.orbit[ii,2]**2./2.
                 for ii in range(len(self.t))]
        plot.bovy_plot(nu.array(self.t),nu.array(self.E)/self.E[0],
                       *args,**kwargs)

    def _callRect(self,*args):
        raise AttributeError("Cannot transform R-only planar orbit to rectangular coordinates")

class planarOrbit(planarOrbitTop):
    """Class representing a full planar orbit (R,vR,vT,phi)"""
    def __init__(self,vxvv=[1.,0.,1.,0.]):
        """
        NAME:
           __init__
        PURPOSE:
           Initialize a planarOrbit
        INPUT:
           vxvv - [R,vR,vT,phi]
        OUTPUT:
        HISTORY:
           2010-07-12 - Written - Bovy (NYU)
        """
        if len(vxvv) == 3:
            raise ValueError("You only provided R,vR, & vT, but not phi; you probably want planarROrbit")
        self.vxvv= vxvv
        return None

    def integrate(self,t,pot):
        """
        NAME:
           integrate
        PURPOSE:
           integrate the orbit
        INPUT:
           t - list of times at which to output (0 has to be in this!)
           pot - potential instance or list of instances
        OUTPUT:
           (none) (get the actual orbit using getOrbit()
        HISTORY:
           2010-07-20
        """
        if isinstance(pot,Potential):
            thispot= RZToplanarPotential(pot)
        else:
            thispot= pot
        self.t= nu.array(t)
        self.orbit= _integrateOrbit(self.vxvv,thispot,t)

    def e(self):
        """
        NAME:
           e
        PURPOSE:
           calculate the eccentricity
        INPUT:
        OUTPUT:
           eccentricity
        HISTORY:
           2010-09-15 - Written - Bovy (NYU)
        """
        if not hasattr(self,'orbit'):
            raise AttributeError("Integrate the orbit first")
        rs= self.orbit[:,0]**2.
        return (nu.amax(rs)-nu.amin(rs))/(nu.amax(rs)+nu.amin(rs))

    def plot(self,*args,**kwargs):
        """
        NAME:
           plot
        PURPOSE:
           plot a planar Orbit
        INPUT:
           bovy_plot args and kwargs
        OUTPUT:
           plpt
        HISTORY:
           2010-09-20 - Written - Bovy (NYU)
        """
        if not kwargs.has_key('xlabel'):
            kwargs['xlabel']= r'$x$'
        if not kwargs.has_key('ylabel'):
            kwargs['ylabel']= r'$y$'
        plot.bovy_plot(self.orbit[:,0]*nu.cos(self.orbit[:,3]),
                       self.orbit[:,0]*nu.sin(self.orbit[:,3]),
                       *args,**kwargs)

    def plotEt(self,pot,*args,**kwargs):
        """
        NAME:
           plotEt
        PURPOSE:
           plot E(t) along the orbit
        INPUT:
           pot - Potential instance or list of instances in which the orbit was
                 integrated
           +bovy_plot.bovy_plot inputs
        OUTPUT:
           figure to output device
        HISTORY:
           2010-07-10 - Written - Bovy (NYU)
        """
        self.E= [evaluateplanarPotentials(self.orbit[ii,0],
                                          self.orbit[ii,3],pot)+
                 self.orbit[ii,1]**2./2.+self.orbit[ii,2]**2./2.
                 for ii in range(len(self.t))]
        plot.bovy_plot(nu.array(self.t),nu.array(self.E)/self.E[0],
                       *args,**kwargs)

    def _callRect(self,*args):
        kwargs= {}
        kwargs['rect']= False
        vxvv= self.__call__(*args,**kwargs)
        x= vxvv[0]*m.cos(vxvv[3])
        y= vxvv[0]*m.sin(vxvv[3])
        vx= vxvv[1]*m.cos(vxvv[5])-vxvv[2]*m.sin(vxvv[5])
        vy= -vxvv[1]*m.sin(vxvv[5])-vxvv[2]*m.cos(vxvv[5])
        return nu.array([x,y,vx,vy])

def _integrateROrbit(vxvv,pot,t):
    """
    NAME:
       _integrateROrbit
    PURPOSE:
       integrate an orbit in a Phi(R) potential in the R-plane
    INPUT:
       vxvv - array with the initial conditions stacked like
              [R,vR,vT]; vR outward!
       pot - Potential instance
       t - list of times at which to output (0 has to be in this!)
    OUTPUT:
       [:,3] array of [R,vR,vT] at each t
    HISTORY:
       2010-07-20 - Written - Bovy (NYU)
    """
    l= vxvv[0]*vxvv[2]
    l2= l**2.
    init= [vxvv[0],vxvv[1]]
    intOut= integrate.odeint(_REOM,init,t,args=(pot,l2),
                             rtol=10.**-8.)#,mxstep=100000000)
    out= nu.zeros((len(t),3))
    out[:,0]= intOut[:,0]
    out[:,1]= intOut[:,1]
    out[:,2]= l/out[:,0]
    return out

def _REOM(y,t,pot,l2):
    """
    NAME:
       _REOM
    PURPOSE:
       implements the EOM, i.e., the right-hand side of the differential 
       equation
    INPUT:
       y - current phase-space position
       t - current time
       pot - (list of) Potential instance(s)
       l2 - angular momentum squared
    OUTPUT:
       dy/dt
    HISTORY:
       2010-07-20 - Written - Bovy (NYU)
    """
    return [y[1],
            l2/y[0]**3.+evaluateplanarRforces(y[0],pot,t=t)]

def _integrateOrbit(vxvv,pot,t):
    """
    NAME:
       _integrateOrbit
    PURPOSE:
       integrate an orbit in a Phi(R) potential in the (R,phi)-plane
    INPUT:
       vxvv - array with the initial conditions stacked like
              [R,vR,vT,phi]; vR outward!
       pot - Potential instance
       t - list of times at which to output (0 has to be in this!)
    OUTPUT:
       [:,4] array of [R,vR,vT,phi] at each t
    HISTORY:
       2010-07-20 - Written - Bovy (NYU)
    """
    vphi= vxvv[2]/vxvv[0]
    init= [vxvv[0],vxvv[1],vxvv[3],vphi]
    intOut= integrate.odeint(_EOM,init,t,args=(pot,),
                             rtol=10.**-8.)#,mxstep=100000000)
    out= nu.zeros((len(t),4))
    out[:,0]= intOut[:,0]
    out[:,1]= intOut[:,1]
    out[:,3]= intOut[:,2]
    out[:,2]= out[:,0]*intOut[:,3]
    return out

def _EOM(y,t,pot):
    """
    NAME:
       _EOM
    PURPOSE:
       implements the EOM, i.e., the right-hand side of the differential 
       equation
    INPUT:
       y - current phase-space position
       t - current time
       pot - (list of) Potential instance(s)
       l2 - angular momentum squared
    OUTPUT:
       dy/dt
    HISTORY:
       2010-07-20 - Written - Bovy (NYU)
    """
    l2= (y[0]**2.*y[3])**2.
    return [y[1],
            l2/y[0]**3.+evaluateplanarRforces(y[0],pot,phi=y[2],t=t),
            y[3],
            1./y[0]**2.*(evaluateplanarphiforces(y[0],pot,phi=y[2],t=t)-
                         2.*y[0]*y[1]*y[3])]
