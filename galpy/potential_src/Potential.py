###############################################################################
#   Potential.py: top-level class for a full potential
#
#   Evaluate by calling the instance: Pot(R,z,phi)
#
#   API for Potentials:
#      function _evaluate(self,R,z,phi) returns Phi(R,z,phi)
#    for orbit integration you need
#      function _Rforce(self,R,z,phi) return -d Phi d R
#      function _zforce(self,R,z,phi) return - d Phi d Z
#    density
#      function _dens(self,R,z,phi) return BOVY??
#    for epicycle frequency
#      function _R2deriv(self,R,z,phi) return d2 Phi dR2
###############################################################################
from __future__  import division, print_function

import os, os.path
import pickle
from functools import wraps
import math
import numpy as nu
from scipy import optimize, integrate
import galpy.util.bovy_plot as plot
from galpy.util import config
from galpy.util.bovy_conversion import velocity_in_kpcGyr, \
    physical_conversion, potential_physical_input, freq_in_Gyr
from galpy.util import bovy_conversion
from galpy.potential_src.plotRotcurve import plotRotcurve, vcirc
from galpy.potential_src.plotEscapecurve import _INF, plotEscapecurve
_APY_LOADED= True
try:
    from astropy import units
except ImportError:
    _APY_LOADED= False
class Potential(object):
    """Top-level class for a potential"""
    def __init__(self,amp=1.,ro=None,vo=None,amp_units=None):
        """
        NAME:
           __init__
        PURPOSE:
        INPUT:
           amp - amplitude to be applied when evaluating the potential and its forces
           amp_units - ('mass', 'velocity2', 'density') type of units that amp should have if it has units
        OUTPUT:
        HISTORY:
        """
        self._amp= amp
        self.dim= 3
        self.isRZ= True
        self.isNonAxi= False
        self.hasC= False
        self.hasC_dxdv= False
        # Parse ro and vo
        if ro is None:
            self._ro= config.__config__.getfloat('normalization','ro')
            self._roSet= False
        else:
            if _APY_LOADED and isinstance(ro,units.Quantity):
                ro= ro.to(units.kpc).value
            self._ro= ro
            self._roSet= True
        if vo is None:
            self._vo= config.__config__.getfloat('normalization','vo')
            self._voSet= False
        else:
            if _APY_LOADED and isinstance(vo,units.Quantity):
                vo= vo.to(units.km/units.s).value
            self._vo= vo
            self._voSet= True
        # Parse amp if it has units
        if _APY_LOADED and isinstance(self._amp,units.Quantity):
            # Try a bunch of possible units
            unitFound= False
            # velocity^2
            try:
                self._amp= self._amp.to(units.km**2/units.s**2).value\
                    /self._vo**2.
            except units.UnitConversionError: pass
            else:
                unitFound= True
                if not amp_units == 'velocity2':
                    raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of velocity2 instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # mass
                try:
                    self._amp= self._amp.to(units.Msun).value\
                        /bovy_conversion.mass_in_msol(self._vo,self._ro)
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'mass':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of mass instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # G x mass
                try:
                    self._amp= self._amp.to(units.pc*units.km**2/units.s**2)\
                        .value\
                        /bovy_conversion.mass_in_msol(self._vo,self._ro)\
                        /bovy_conversion._G
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'mass':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of G x mass instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # density
                try:
                    self._amp= self._amp.to(units.Msun/units.pc**3).value\
                        /bovy_conversion.dens_in_msolpc3(self._vo,self._ro)
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'density':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of density instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # G x density
                try:
                    self._amp= self._amp.to(units.km**2/units.s**2\
                                                /units.pc**2).value\
                        /bovy_conversion.dens_in_msolpc3(self._vo,self._ro)\
                        /bovy_conversion._G
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'density':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of G x density instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # surface density
                try:
                    self._amp= self._amp.to(units.Msun/units.pc**2).value\
                        /bovy_conversion.surfdens_in_msolpc2(self._vo,self._ro)
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'surfacedensity':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of surface density instead' % (type(self).__name__,amp_units))
            if not unitFound:
                # G x surface density
                try:
                    self._amp= self._amp.to(units.km**2/units.s**2\
                                                /units.pc).value\
                        /bovy_conversion.surfdens_in_msolpc2(self._vo,self._ro)\
                        /bovy_conversion._G
                except units.UnitConversionError: pass
                else:
                    unitFound= True
                    if not amp_units == 'surfacedensity':
                        raise units.UnitConversionError('amp= parameter of %s should have units of %s, but has units of G x surface density instead' % (type(self).__name__,amp_units))
            if not unitFound:
                raise units.UnitConversionError('amp= parameter of %s should have units of %s; given units are not understood' % (type(self).__name__,amp_units))    
            else:
                # When amplitude is given with units, turn on physical output
                self._roSet= True
                self._voSet= True
        return None

    def turn_physical_off(self):
        """
        NAME:

           turn_physical_off

        PURPOSE:

           turn off automatic returning of outputs in physical units

        INPUT:

           (none)

        OUTPUT:

           (none)

        HISTORY:

           2016-01-30 - Written - Bovy (UofT)

        """
        self._roSet= False
        self._voSet= False
        return None

    def turn_physical_on(self,ro=None,vo=None):
        """
        NAME:

           turn_physical_on

        PURPOSE:

           turn on automatic returning of outputs in physical units

        INPUT:

           ro= reference distance (kpc; can be Quantity)

           vo= reference velocity (km/s; can be Quantity)

        OUTPUT:

           (none)

        HISTORY:

           2016-01-30 - Written - Bovy (UofT)

        """
        self._roSet= True
        self._voSet= True
        if not ro is None:
            if _APY_LOADED and isinstance(ro,units.Quantity):
                ro= ro.to(units.kpc).value
            self._ro= ro
        if not vo is None:
            if _APY_LOADED and isinstance(vo,units.Quantity):
                vo= vo.to(units.km/units.s).value
            self._vo= vo
        return None

    @potential_physical_input
    @physical_conversion('energy',pop=True)
    def __call__(self,R,z,phi=0.,t=0.,dR=0,dphi=0):
        """
        NAME:

           __call__

        PURPOSE:

           evaluate the potential at (R,z,phi,t)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (optional; can be Quantity)

           t - time (optional; can be Quantity)

        OUTPUT:

           Phi(R,z,t)

        HISTORY:

           2010-04-16 - Written - Bovy (NYU)

        """
        return self._call_nodecorator(R,z,phi=phi,t=t,dR=dR,dphi=dphi)

    def _call_nodecorator(self,R,z,phi=0.,t=0.,dR=0.,dphi=0):
        if dR == 0 and dphi == 0:
            try:
                rawOut= self._evaluate(R,z,phi=phi,t=t)
            except AttributeError: #pragma: no cover
                raise PotentialError("'_evaluate' function not implemented for this potential")
            if rawOut is None: return rawOut
            else: return self._amp*rawOut
        elif dR == 1 and dphi == 0:
            return -self.Rforce(R,z,phi=phi,t=t,use_physical=False)
        elif dR == 0 and dphi == 1:
            return -self.phiforce(R,z,phi=phi,t=t,use_physical=False)
        elif dR == 2 and dphi == 0:
            return self.R2deriv(R,z,phi=phi,t=t,use_physical=False)
        elif dR == 0 and dphi == 2:
            return self.phi2deriv(R,z,phi=phi,t=t,use_physical=False)
        elif dR == 1 and dphi == 1:
            return self.Rphideriv(R,z,phi=phi,t=t,use_physical=False)
        elif dR != 0 or dphi != 0:
            raise NotImplementedError('Higher-order derivatives not implemented for this potential')
        
    @potential_physical_input
    @physical_conversion('force',pop=True)
    def Rforce(self,R,z,phi=0.,t=0.):
        """
        NAME:

           Rforce

        PURPOSE:

           evaluate cylindrical radial force F_R  (R,z)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (optional; can be Quantity)

           t - time (optional; can be Quantity)

        OUTPUT:

           F_R (R,z,phi,t)

        HISTORY:

           2010-04-16 - Written - Bovy (NYU)

        """
        return self._Rforce_nodecorator(R,z,phi=phi,t=t)

    def _Rforce_nodecorator(self,R,z,phi=0.,t=0.):
        # Separate, so it can be used during orbit integration
        try:
            return self._amp*self._Rforce(R,z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            raise PotentialError("'_Rforce' function not implemented for this potential")
        
    @potential_physical_input
    @physical_conversion('force',pop=True)
    def zforce(self,R,z,phi=0.,t=0.):
        """
        NAME:

           zforce

        PURPOSE:

           evaluate the vertical force F_z  (R,z,t)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (optional; can be Quantity)

           t - time (optional; can be Quantity)

        OUTPUT:

           F_z (R,z,phi,t)

        HISTORY:

           2010-04-16 - Written - Bovy (NYU)

        """
        return self._zforce_nodecorator(R,z,phi=phi,t=t)

    def _zforce_nodecorator(self,R,z,phi=0.,t=0.):
        # Separate, so it can be used during orbit integration
        try:
            return self._amp*self._zforce(R,z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            raise PotentialError("'_zforce' function not implemented for this potential")

    @potential_physical_input
    @physical_conversion('force',pop=True)
    def rforce(self,R,z,phi=0.,t=0.):
        """
        NAME:

           rforce

        PURPOSE:

           evaluate spherical radial force F_r  (R,z)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (optional; can be Quantity)

           t - time (optional; can be Quantity)

        OUTPUT:

           F_r (R,z,phi,t)

        HISTORY:

           2016-06-20 - Written - Bovy (UofT)

        """
        r= nu.sqrt(R**2.+z**2.)
        return self.Rforce(R,z,phi=phi,t=t,use_physical=False)*R/r\
            +self.zforce(R,z,phi=phi,t=t,use_physical=False)*z/r
        
    @potential_physical_input
    @physical_conversion('density',pop=True)
    def dens(self,R,z,phi=0.,t=0.,forcepoisson=False):
        """
        NAME:

           dens

        PURPOSE:

           evaluate the density rho(R,z,t)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (optional; can be Quantity)

           t - time (optional; can be Quantity)

        KEYWORDS:

           forcepoisson= if True, calculate the density through the Poisson equation, even if an explicit expression for the density exists

        OUTPUT:

           rho (R,z,phi,t)

        HISTORY:

           2010-08-08 - Written - Bovy (NYU)

        """
        try:
            if forcepoisson: raise AttributeError #Hack!
            return self._amp*self._dens(R,z,phi=phi,t=t)
        except AttributeError:
            #Use the Poisson equation to get the density
            return (-self.Rforce(R,z,phi=phi,t=t,use_physical=False)/R
                     +self.R2deriv(R,z,phi=phi,t=t,use_physical=False)
                     +self.phi2deriv(R,z,phi=phi,t=t,use_physical=False)/R**2.
                     +self.z2deriv(R,z,phi=phi,t=t,use_physical=False))/4./nu.pi

    @potential_physical_input
    @physical_conversion('mass',pop=True)
    def mass(self,R,z=None,t=0.,forceint=False):
        """
        NAME:

           mass

        PURPOSE:

           evaluate the mass enclosed

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z= (None) vertical height (can be Quantity)

           t - time (optional; can be Quantity)

        KEYWORDS:

           forceint= if True, calculate the mass through integration of the density, even if an explicit expression for the mass exists

        OUTPUT:

           1) for spherical potentials: M(<R) [or if z is None], when the mass is implemented explicitly, the mass enclosed within  r = sqrt(R^2+z^2) is returned when not z is None; forceint will integrate between -z and z, so the two are inconsistent (If you care to have this changed, raise an issue on github)

           2) for axisymmetric potentials: M(<R,<fabs(Z))

        HISTORY:

           2014-01-29 - Written - Bovy (IAS)

        """
        if self.isNonAxi:
            raise NotImplementedError('mass for non-axisymmetric potentials is not currently supported')
        try:
            if forceint: raise AttributeError #Hack!
            return self._amp*self._mass(R,z=z,t=t)
        except AttributeError:
            #Use numerical integration to get the mass
            if z is None:
                return 4.*nu.pi\
                    *integrate.quad(lambda x: x**2.\
                                        *self.dens(x,0.,
                                                  use_physical=False),
                                    0.,R)[0]
            else:
                return 4.*nu.pi\
                    *integrate.dblquad(lambda y,x: x\
                                           *self.dens(x,y,use_physical=False),
                                       0.,R,lambda x: 0., lambda x: z)[0]

    @physical_conversion('mass',pop=True)
    def mvir(self,H=70.,Om=0.3,overdens=200.,wrtcrit=False,
             forceint=False):
        """
        NAME:

           mvir

        PURPOSE:

           calculate the virial mass

        INPUT:

           H= (default: 70) Hubble constant in km/s/Mpc
           
           Om= (default: 0.3) Omega matter
       
           overdens= (200) overdensity which defines the virial radius

           wrtcrit= (False) if True, the overdensity is wrt the critical density rather than the mean matter density
           
           ro= distance scale in kpc or as Quantity (default: object-wide, which if not set is 8 kpc))

           vo= velocity scale in km/s or as Quantity (default: object-wide, which if not set is 220 km/s))

        KEYWORDS:

           forceint= if True, calculate the mass through integration of the density, even if an explicit expression for the mass exists

        OUTPUT:

           M(<rvir)

        HISTORY:

           2014-09-12 - Written - Bovy (IAS)

        """
        #Evaluate the virial radius
        try:
            rvir= self.rvir(H=H,Om=Om,overdens=overdens,wrtcrit=wrtcrit,
                            use_physical=False)
        except AttributeError:
            raise AttributeError("This potential does not have a '_scale' defined to base the concentration on or does not support calculating the virial radius")
        return self.mass(rvir,forceint=forceint,use_physical=False)

    @potential_physical_input
    @physical_conversion('forcederivative',pop=True)
    def R2deriv(self,R,Z,phi=0.,t=0.):
        """
        NAME:

           R2deriv

        PURPOSE:

           evaluate the second radial derivative

        INPUT:

           R - Galactocentric radius (can be Quantity)

           Z - vertical height (can be Quantity)

           phi - Galactocentric azimuth (can be Quantity)

           t - time (can be Quantity)

        OUTPUT:

           d2phi/dR2

        HISTORY:

           2011-10-09 - Written - Bovy (IAS)

        """
        try:
            return self._amp*self._R2deriv(R,Z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            raise PotentialError("'_R2deriv' function not implemented for this potential")      

    @potential_physical_input
    @physical_conversion('forcederivative',pop=True)
    def z2deriv(self,R,Z,phi=0.,t=0.):
        """
        NAME:

           z2deriv

        PURPOSE:

           evaluate the second vertical derivative

        INPUT:

           R - Galactocentric radius (can be Quantity)

           Z - vertical height (can be Quantity)

           phi - Galactocentric azimuth (can be Quantity)

           t - time (can be Quantity)

        OUTPUT:

           d2phi/dz2

        HISTORY:

           2012-07-25 - Written - Bovy (IAS@MPIA)

        """
        try:
            return self._amp*self._z2deriv(R,Z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            raise PotentialError("'_z2deriv' function not implemented for this potential")      

    @potential_physical_input
    @physical_conversion('forcederivative',pop=True)
    def Rzderiv(self,R,Z,phi=0.,t=0.):
        """
        NAME:

           Rzderiv

        PURPOSE:

           evaluate the mixed R,z derivative

        INPUT:

           R - Galactocentric radius (can be Quantity)

           Z - vertical height (can be Quantity)

           phi - Galactocentric azimuth (can be Quantity)

           t - time (can be Quantity)

        OUTPUT:

           d2phi/dz/dR

        HISTORY:

           2013-08-26 - Written - Bovy (IAS)

        """
        try:
            return self._amp*self._Rzderiv(R,Z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            raise PotentialError("'_Rzderiv' function not implemented for this potential")      

    def normalize(self,norm,t=0.):
        """
        NAME:

           normalize

        PURPOSE:

           normalize a potential in such a way that vc(R=1,z=0)=1., or a 
           fraction of this

        INPUT:

           norm - normalize such that Rforce(R=1,z=0) is such that it is 'norm' of the force necessary to make vc(R=1,z=0)=1 (if True, norm=1)

        OUTPUT:
           
           (none)

        HISTORY:


           2010-07-10 - Written - Bovy (NYU)

        """
        self._amp*= norm/nu.fabs(self.Rforce(1.,0.,t=t,use_physical=False))

    @potential_physical_input
    @physical_conversion('force',pop=True)
    def phiforce(self,R,z,phi=0.,t=0.):
        """
        NAME:

           phiforce

        PURPOSE:

           evaluate the azimuthal force F_phi  (R,z,phi,t)

        INPUT:

           R - Cylindrical Galactocentric radius (can be Quantity)

           z - vertical height (can be Quantity)

           phi - azimuth (rad; can be Quantity)

           t - time (optional; can be Quantity)

        OUTPUT:

           F_phi (R,z,phi,t)

        HISTORY:

           2010-07-10 - Written - Bovy (NYU)

        """
        return self._phiforce_nodecorator(R,z,phi=phi,t=t)

    def _phiforce_nodecorator(self,R,z,phi=0.,t=0.):
        # Separate, so it can be used during orbit integration
        try:
            return self._amp*self._phiforce(R,z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            if self.isNonAxi:
                raise PotentialError("'_phiforce' function not implemented for this non-axisymmetric potential")
            return 0.

    @potential_physical_input
    @physical_conversion('forcederivative',pop=True)
    def phi2deriv(self,R,Z,phi=0.,t=0.):
        """
        NAME:

           phi2deriv

        PURPOSE:

           evaluate the second azimuthal derivative

        INPUT:

           R - Galactocentric radius (can be Quantity)

           Z - vertical height (can be Quantity)

           phi - Galactocentric azimuth (can be Quantity)

           t - time (can be Quantity)

        OUTPUT:

           d2Phi/dphi2

        HISTORY:

           2013-09-24 - Written - Bovy (IAS)

        """
        try:
            return self._amp*self._phi2deriv(R,Z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            if self.isNonAxi:
                raise PotentialError("'_phiforce' function not implemented for this non-axisymmetric potential")
            return 0.

    @potential_physical_input
    @physical_conversion('forcederivative',pop=True)
    def Rphideriv(self,R,Z,phi=0.,t=0.):
        """
        NAME:

           Rphideriv

        PURPOSE:

           evaluate the mixed radial, azimuthal derivative

        INPUT:

           R - Galactocentric radius (can be Quantity)

           Z - vertical height (can be Quantity)

           phi - Galactocentric azimuth (can be Quantity)

           t - time (can be Quantity)

        OUTPUT:

           d2Phi/dphidR

        HISTORY:

           2014-06-30 - Written - Bovy (IAS)

        """
        try:
            return self._amp*self._Rphideriv(R,Z,phi=phi,t=t)
        except AttributeError: #pragma: no cover
            if self.isNonAxi:
                raise PotentialError("'_phiforce' function not implemented for this non-axisymmetric potential")
            return 0.

    def toPlanar(self):
        """
        NAME:

           toPlanar

        PURPOSE:

           convert a 3D potential into a planar potential in the mid-plane

        INPUT:

           (none)

        OUTPUT:

           planarPotential

        HISTORY:

           unknown

        """
        from galpy.potential import toPlanarPotential
        return toPlanarPotential(self)

    def toVertical(self,R):
        """
        NAME:

           toVertical

        PURPOSE:

           convert a 3D potential into a linear (vertical) potential at R

        INPUT:

           R - Galactocentric radius at which to create the vertical potential (can be Quantity)

        OUTPUT:

           linear (vertical) potential

        HISTORY

           unknown

        """
        if _APY_LOADED and isinstance(R,units.Quantity):
            R= R.to(units.kpc).value/self._ro
        from galpy.potential import RZToverticalPotential
        return RZToverticalPotential(self,R)

    def plot(self,t=0.,rmin=0.,rmax=1.5,nrs=21,zmin=-0.5,zmax=0.5,nzs=21,
             effective=False,Lz=None,phi=None,
             xrange=None,yrange=None,
             justcontours=False,
             ncontours=21,savefilename=None):
        """
        NAME:

           plot

        PURPOSE:

           plot the potential

        INPUT:

           t= time tp plot potential at

           rmin= minimum R at which to calculate (can be Quantity)

           rmax= maximum R (can be Quantity)

           nrs= grid in R

           zmin= minimum z (can be Quantity)

           zmax= maximum z (can be Quantity)

           nzs= grid in z

           phi= (None) azimuth to use for non-axisymmetric potentials

           effective= (False) if True, plot the effective potential Phi + Lz^2/2/R^2

           Lz= (None) angular momentum to use for the effective potential when effective=True

           ncontours - number of contours

           justcontours= (False) if True, just plot contours

           savefilename - save to or restore from this savefile (pickle)

           xrange, yrange= can be specified independently from rmin,zmin, etc.

        OUTPUT:

           plot to output device

        HISTORY:

           2010-07-09 - Written - Bovy (NYU)

           2014-04-08 - Added effective= - Bovy (IAS)

        """
        if _APY_LOADED:
            if isinstance(rmin,units.Quantity):
                rmin= rmin.to(units.kpc).value/self._ro
            if isinstance(rmax,units.Quantity):
                rmax= rmax.to(units.kpc).value/self._ro
            if isinstance(zmin,units.Quantity):
                zmin= zmin.to(units.kpc).value/self._ro
            if isinstance(zmax,units.Quantity):
                zmax= zmax.to(units.kpc).value/self._ro
        if xrange is None: xrange= [rmin,rmax]
        if yrange is None: yrange= [zmin,zmax]
        if not savefilename is None and os.path.exists(savefilename):
            print("Restoring savefile "+savefilename+" ...")
            savefile= open(savefilename,'rb')
            potRz= pickle.load(savefile)
            Rs= pickle.load(savefile)
            zs= pickle.load(savefile)
            savefile.close()
        else:
            if effective and Lz is None:
                raise RuntimeError("When effective=True, you need to specify Lz=")
            Rs= nu.linspace(xrange[0],xrange[1],nrs)
            zs= nu.linspace(yrange[0],yrange[1],nzs)
            potRz= nu.zeros((nrs,nzs))
            for ii in range(nrs):
                for jj in range(nzs):
                    potRz[ii,jj]= evaluatePotentials(self,
                                                     Rs[ii],zs[jj],t=t,phi=phi,
                                                     use_physical=False)
                if effective:
                    potRz[ii,:]+= 0.5*Lz**2/Rs[ii]**2.
            #Don't plot outside of the desired range
            potRz[Rs < rmin,:]= nu.nan
            potRz[Rs > rmax,:]= nu.nan
            potRz[:,zs < zmin]= nu.nan
            potRz[:,zs > zmax]= nu.nan
            if not savefilename == None:
                print("Writing savefile "+savefilename+" ...")
                savefile= open(savefilename,'wb')
                pickle.dump(potRz,savefile)
                pickle.dump(Rs,savefile)
                pickle.dump(zs,savefile)
                savefile.close()
        return plot.bovy_dens2d(potRz.T,origin='lower',cmap='gist_gray',contours=True,
                                xlabel=r"$R/R_0$",ylabel=r"$z/R_0$",
                                xrange=xrange,
                                yrange=yrange,
                                aspect=.75*(rmax-rmin)/(zmax-zmin),
                                cntrls='-',
                                justcontours=justcontours,
                                levels=nu.linspace(nu.nanmin(potRz),nu.nanmax(potRz),
                                                   ncontours))
        
    def plotDensity(self,rmin=0.,rmax=1.5,nrs=21,zmin=-0.5,zmax=0.5,nzs=21,
                    phi=None,
                    ncontours=21,savefilename=None,aspect=None,log=False,
                    justcontours=False):
        """
        NAME:

           plotDensity

        PURPOSE:

           plot the density of this potential

        INPUT:

           rmin= minimum R (can be Quantity)

           rmax= maximum R (can be Quantity)

           nrs= grid in R

           zmin= minimum z (can be Quantity)

           zmax= maximum z (can be Quantity)

           nzs= grid in z

           phi= (None) azimuth to use for non-axisymmetric potentials

           ncontours= number of contours

           justcontours= (False) if True, just plot contours

           savefilename= save to or restore from this savefile (pickle)

           log= if True, plot the log density

        OUTPUT:

           plot to output device

        HISTORY:

           2014-01-05 - Written - Bovy (IAS)

        """
        return plotDensities(self,rmin=rmin,rmax=rmax,nrs=nrs,
                             zmin=zmin,zmax=zmax,nzs=nzs,phi=phi,
                             ncontours=ncontours,savefilename=savefilename,
                             justcontours=justcontours,
                             aspect=aspect,log=log)

    @potential_physical_input
    @physical_conversion('velocity',pop=True)
    def vcirc(self,R,phi=None):
        """
        
        NAME:
        
            vcirc
        
        PURPOSE:
        
            calculate the circular velocity at R in this potential

        INPUT:
        
            R - Galactocentric radius (can be Quantity)
        
            phi= (None) azimuth to use for non-axisymmetric potentials

        OUTPUT:
        
            circular rotation velocity
        
        HISTORY:
        
            2011-10-09 - Written - Bovy (IAS)
        
       2016-06-15 - Added phi= keyword for non-axisymmetric potential - Bovy (UofT)

        """
        return nu.sqrt(R*-self.Rforce(R,0.,phi=phi,use_physical=False))

    @potential_physical_input
    @physical_conversion('frequency',pop=True)
    def dvcircdR(self,R,phi=None):
        """
        
        NAME:
        
            dvcircdR
        
        PURPOSE:
        
            calculate the derivative of the circular velocity at R wrt R
            in this potential

        INPUT:
        
            R - Galactocentric radius (can be Quantity)
        
            phi= (None) azimuth to use for non-axisymmetric potentials

        OUTPUT:
        
            derivative of the circular rotation velocity wrt R
        
        HISTORY:
        
            2013-01-08 - Written - Bovy (IAS)
        
            2016-06-28 - Added phi= keyword for non-axisymmetric potential - Bovy (UofT)

        """
        return 0.5*(-self.Rforce(R,0.,phi=phi,use_physical=False)\
                         +R*self.R2deriv(R,0.,phi=phi,use_physical=False))\
                         /self.vcirc(R,phi=phi,use_physical=False)

    @potential_physical_input
    @physical_conversion('frequency',pop=True)
    def omegac(self,R):
        """
        
        NAME:
        
            omegac
        
        PURPOSE:
        
            calculate the circular angular speed at R in this potential

        INPUT:
        
            R - Galactocentric radius (can be Quantity)
        
        OUTPUT:
        
            circular angular speed
        
        HISTORY:
        
            2011-10-09 - Written - Bovy (IAS)
        
        """
        return nu.sqrt(-self.Rforce(R,0.,use_physical=False)/R)

    @potential_physical_input
    @physical_conversion('frequency',pop=True)
    def epifreq(self,R):
        """
        
        NAME:
        
           epifreq
        
        PURPOSE:
        
           calculate the epicycle frequency at R in this potential
        
        INPUT:
        
           R - Galactocentric radius (can be Quantity)
        
        OUTPUT:
        
           epicycle frequency
        
        HISTORY:
        
           2011-10-09 - Written - Bovy (IAS)
        
        """
        return nu.sqrt(self.R2deriv(R,0.,use_physical=False)\
                           -3./R*self.Rforce(R,0.,use_physical=False))

    @potential_physical_input
    @physical_conversion('frequency',pop=True)
    def verticalfreq(self,R):
        """
        
        NAME:
        
           verticalfreq
        
        PURPOSE:
        
           calculate the vertical frequency at R in this potential
        
        INPUT:
        
           R - Galactocentric radius (can be Quantity)
        
        OUTPUT:
        
           vertical frequency
        
        HISTORY:
        
           2012-07-25 - Written - Bovy (IAS@MPIA)
        
        """
        return nu.sqrt(self.z2deriv(R,0.,use_physical=False))

    @physical_conversion('position',pop=True)
    def lindbladR(self,OmegaP,m=2,**kwargs):
        """
        
        NAME:
        
           lindbladR
        
        PURPOSE:
        
            calculate the radius of a Lindblad resonance
        
        INPUT:
        
           OmegaP - pattern speed (can be Quantity)

           m= order of the resonance (as in m(O-Op)=kappa (negative m for outer)
              use m='corotation' for corotation
              +scipy.optimize.brentq xtol,rtol,maxiter kwargs
        
        OUTPUT:
        
           radius of Linblad resonance, None if there is no resonance
        
        HISTORY:
        
           2011-10-09 - Written - Bovy (IAS)
        
        """
        if _APY_LOADED and isinstance(OmegaP,units.Quantity):
            OmegaP= OmegaP.to(1/units.Gyr).value/freq_in_Gyr(self._vo,self._ro)
        return lindbladR(self,OmegaP,m=m,use_physical=False,**kwargs)

    @potential_physical_input
    @physical_conversion('velocity',pop=True)
    def vesc(self,R):
        """

        NAME:

            vesc

        PURPOSE:

            calculate the escape velocity at R for this potential

        INPUT:

            R - Galactocentric radius (can be Quantity)

        OUTPUT:

            escape velocity

        HISTORY:

            2011-10-09 - Written - Bovy (IAS)

        """
        return nu.sqrt(2.*(self(_INF,0.,use_physical=False)\
                               -self(R,0.,use_physical=False)))
        
    @physical_conversion('position',pop=True)
    def rl(self,lz):
        """
        NAME:
        
            rl
        
        PURPOSE:
        
            calculate the radius of a circular orbit of Lz
        
        INPUT:
        
        
            lz - Angular momentum (can be Quantity)
        
        OUTPUT:
        
            radius
        
        HISTORY:
        
            2012-07-30 - Written - Bovy (IAS@MPIA)
        
        NOTE:
        
            seems to take about ~0.5 ms for a Miyamoto-Nagai potential; 
            ~0.75 ms for a MWPotential
        
        """
        if _APY_LOADED and isinstance(lz,units.Quantity):
            lz= lz.to(units.km/units.s*units.kpc).value/self._vo/self._ro
        return rl(self,lz,use_physical=False)

    @potential_physical_input
    @physical_conversion('dimensionless',pop=True)
    def flattening(self,R,z):
        """
        
        NAME:
        
           flattening
        
        PURPOSE:
        
           calculate the potential flattening, defined as sqrt(fabs(z/R F_R/F_z))
        
        INPUT:
        
           R - Galactocentric radius (can be Quantity)

           z - height (can be Quantity)
        
        OUTPUT:
        
           flattening
        
        HISTORY:
        
           2012-09-13 - Written - Bovy (IAS)
        
        """
        return nu.sqrt(nu.fabs(z/R*self.Rforce(R,z,use_physical=False)\
                                   /self.zforce(R,z,use_physical=False)))

    @physical_conversion('velocity',pop=True)
    def vterm(self,l,deg=True):
        """
        
        NAME:
        
            vterm
        
        PURPOSE:
        
            calculate the terminal velocity at l in this potential

        INPUT:
        
            l - Galactic longitude [deg/rad; can be Quantity)

            deg= if True (default), l in deg
        
        OUTPUT:
        
            terminal velocity
        
        HISTORY:
        
            2013-05-31 - Written - Bovy (IAS)
        
        """
        if _APY_LOADED and isinstance(l,units.Quantity):
            l= l.to(units.rad).value
            deg= False
        if deg:
            sinl= nu.sin(l/180.*nu.pi)
        else:
            sinl= nu.sin(l)
        return sinl*(self.omegac(sinl,use_physical=False)\
                         -self.omegac(1.,use_physical=False))

    def plotRotcurve(self,*args,**kwargs):
        """
        NAME:

           plotRotcurve

        PURPOSE:

           plot the rotation curve for this potential (in the z=0 plane for
           non-spherical potentials)

        INPUT:

           Rrange - range (can be Quantity)

           grid= number of points to plot

           savefilename=- save to or restore from this savefile (pickle)

           +bovy_plot(*args,**kwargs)

        OUTPUT:

           plot to output device

        HISTORY:

           2010-07-10 - Written - Bovy (NYU)

        """
        return plotRotcurve(self,*args,**kwargs)

    def plotEscapecurve(self,*args,**kwargs):
        """
        NAME:

           plotEscapecurve

        PURPOSE:

           plot the escape velocity  curve for this potential 
           (in the z=0 plane for non-spherical potentials)

        INPUT:

           Rrange - range (can be Quantity)

           grid= number of points to plot

           savefilename= save to or restore from this savefile (pickle)

           +bovy_plot(*args,**kwargs)

        OUTPUT:

           plot to output device

        HISTORY:

           2010-08-08 - Written - Bovy (NYU)

        """
        return plotEscapecurve(self.toPlanar(),*args,**kwargs)

    def conc(self,H=70.,Om=0.3,overdens=200.,wrtcrit=False):
        """
        NAME:

           conc

        PURPOSE:

           return the concentration

        INPUT:

           H= (default: 70) Hubble constant in km/s/Mpc
           
           Om= (default: 0.3) Omega matter
       
           overdens= (200) overdensity which defines the virial radius

           wrtcrit= (False) if True, the overdensity is wrt the critical density rather than the mean matter density
           
           ro= distance scale in kpc or as Quantity (default: object-wide, which if not set is 8 kpc))

           vo= velocity scale in km/s or as Quantity (default: object-wide, which if not set is 220 km/s))

        OUTPUT:

           concentration (scale/rvir)

        HISTORY:

           2014-04-03 - Written - Bovy (IAS)

        """
        try:
            return self.rvir(H=H,Om=Om,overdens=overdens,wrtcrit=wrtcrit,
                             use_physical=False)/self._scale
        except AttributeError:
            raise AttributeError("This potential does not have a '_scale' defined to base the concentration on or does not support calculating the virial radius")

    def nemo_accname(self):
        """
        NAME:

           nemo_accname

        PURPOSE:

           return the accname potential name for use of this potential with NEMO

        INPUT:

           (none)

        OUTPUT:

           Acceleration name

        HISTORY:

           2014-12-18 - Written - Bovy (IAS)

        """
        try:
            return self._nemo_accname
        except AttributeError:
            raise AttributeError('NEMO acceleration name not supported for %s' % self.__class__.__name__)

    def nemo_accpars(self,vo,ro):
        """
        NAME:

           nemo_accpars

        PURPOSE:

           return the accpars potential parameters for use of this potential with NEMO

        INPUT:

           vo - velocity unit in km/s

           ro - length unit in kpc

        OUTPUT:

           accpars string

        HISTORY:

           2014-12-18 - Written - Bovy (IAS)

        """
        try:
            return self._nemo_accpars(vo,ro)
        except AttributeError:
            raise AttributeError('NEMO acceleration parameters not supported for %s' % self.__class__.__name__)

class PotentialError(Exception): #pragma: no cover
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

@potential_physical_input
@physical_conversion('energy',pop=True)
def evaluatePotentials(Pot,R,z,phi=None,t=0.,dR=0,dphi=0):
    """
    NAME:

       evaluatePotentials

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (can be Quantity)

       t - time (can be Quantity)

       dR= dphi=, if set to non-zero integers, return the dR, dphi't derivative instead

    OUTPUT:

       Phi(R,z)

    HISTORY:

       2010-04-16 - Written - Bovy (NYU)

    """
    return _evaluatePotentials(Pot,R,z,phi=phi,t=t,dR=dR,dphi=dphi)

def _evaluatePotentials(Pot,R,z,phi=None,t=0.,dR=0,dphi=0):
    """Raw, undecorated function for internal use"""
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    isList= isinstance(Pot,list)
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot._call_nodecorator(R,z,phi=phi,t=t,dR=dR,dphi=dphi)
        return sum
    elif isinstance(Pot,Potential):
        return Pot._call_nodecorator(R,z,phi=phi,t=t,dR=dR,dphi=dphi)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluatePotentials' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('density',pop=True)
def evaluateDensities(Pot,R,z,phi=None,t=0.,forcepoisson=False):
    """
    NAME:

       evaluateDensities

    PURPOSE:

       convenience function to evaluate a possible sum of densities

    INPUT:

       Pot - potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (can be Quantity)

       t - time (can be Quantity)

       forcepoisson= if True, calculate the density through the Poisson equation, even if an explicit expression for the density exists

    OUTPUT:

       rho(R,z)

    HISTORY:

       2010-08-08 - Written - Bovy (NYU)

       2013-12-28 - Added forcepoisson - Bovy (IAS)

    """
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot.dens(R,z,phi=phi,t=t,forcepoisson=forcepoisson,
                           use_physical=False)
        return sum
    elif isinstance(Pot,Potential):
        return Pot.dens(R,z,phi=phi,t=t,forcepoisson=forcepoisson,
                        use_physical=False)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluateDensities' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('force',pop=True)
def evaluateRforces(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluateRforce

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity))

       t - time (optional; can be Quantity)

    OUTPUT:

       F_R(R,z,phi,t)

    HISTORY:

       2010-04-16 - Written - Bovy (NYU)

    """
    return _evaluateRforces(Pot,R,z,phi=phi,t=t)

def _evaluateRforces(Pot,R,z,phi=None,t=0.):
    """Raw, undecorated function for internal use"""
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot._Rforce_nodecorator(R,z,phi=phi,t=t)
        return sum
    elif isinstance(Pot,Potential):
        return Pot._Rforce_nodecorator(R,z,phi=phi,t=t)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluateRforces' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('force',pop=True)
def evaluatephiforces(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluatephiforces

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:
       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       F_phi(R,z,phi,t)

    HISTORY:

       2010-04-16 - Written - Bovy (NYU)

    """
    return _evaluatephiforces(Pot,R,z,phi=phi,t=t)

def _evaluatephiforces(Pot,R,z,phi=None,t=0.):
    """Raw, undecorated function for internal use"""
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot._phiforce_nodecorator(R,z,phi=phi,t=t)
        return sum
    elif isinstance(Pot,Potential):
        return Pot._phiforce_nodecorator(R,z,phi=phi,t=t)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluatephiforces' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('force',pop=True)
def evaluatezforces(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluatezforces

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       F_z(R,z,phi,t)

    HISTORY:

       2010-04-16 - Written - Bovy (NYU)

    """
    return _evaluatezforces(Pot,R,z,phi=phi,t=t)

def _evaluatezforces(Pot,R,z,phi=None,t=0.):
    """Raw, undecorated function for internal use"""
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot._zforce_nodecorator(R,z,phi=phi,t=t)
        return sum
    elif isinstance(Pot,Potential):
        return Pot._zforce_nodecorator(R,z,phi=phi,t=t)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluatezforces' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('force',pop=True)
def evaluaterforces(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluaterforces

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       F_r(R,z,phi,t)

    HISTORY:

       2016-06-10 - Written - Bovy (UofT)

    """
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot.rforce(R,z,phi=phi,t=t,use_physical=False)
        return sum
    elif isinstance(Pot,Potential):
        return Pot.rforce(R,z,phi=phi,t=t,use_physical=False)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluaterforces' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('forcederivative',pop=True)
def evaluateR2derivs(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluateR2derivs

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       d2Phi/d2R(R,z,phi,t)

    HISTORY:

       2012-07-25 - Written - Bovy (IAS)

    """
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot.R2deriv(R,z,phi=phi,t=t,use_physical=False)
        return sum
    elif isinstance(Pot,Potential):
        return Pot.R2deriv(R,z,phi=phi,t=t,use_physical=False)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluateR2derivs' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('forcederivative',pop=True)
def evaluatez2derivs(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluatez2derivs

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       d2Phi/d2z(R,z,phi,t)

    HISTORY:

       2012-07-25 - Written - Bovy (IAS)

    """
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot.z2deriv(R,z,phi=phi,t=t,use_physical=False)
        return sum
    elif isinstance(Pot,Potential):
        return Pot.z2deriv(R,z,phi=phi,t=t,use_physical=False)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluatez2derivs' is neither a Potential-instance or a list of such instances")

@potential_physical_input
@physical_conversion('forcederivative',pop=True)
def evaluateRzderivs(Pot,R,z,phi=None,t=0.):
    """
    NAME:

       evaluateRzderivs

    PURPOSE:

       convenience function to evaluate a possible sum of potentials

    INPUT:

       Pot - a potential or list of potentials

       R - cylindrical Galactocentric distance (can be Quantity)

       z - distance above the plane (can be Quantity)

       phi - azimuth (optional; can be Quantity)

       t - time (optional; can be Quantity)

    OUTPUT:

       d2Phi/dz/dR(R,z,phi,t)

    HISTORY:

       2013-08-28 - Written - Bovy (IAS)

    """
    isList= isinstance(Pot,list)
    nonAxi= _isNonAxi(Pot)
    if nonAxi and phi is None:
        raise PotentialError("The (list of) Potential instances is non-axisymmetric, but you did not provide phi")
    if isList:
        sum= 0.
        for pot in Pot:
            sum+= pot.Rzderiv(R,z,phi=phi,t=t,use_physical=False)
        return sum
    elif isinstance(Pot,Potential):
        return Pot.Rzderiv(R,z,phi=phi,t=t,use_physical=False)
    else: #pragma: no cover 
        raise PotentialError("Input to 'evaluateRzderivs' is neither a Potential-instance or a list of such instances")

def plotPotentials(Pot,rmin=0.,rmax=1.5,nrs=21,zmin=-0.5,zmax=0.5,nzs=21,
                   phi=None,ncontours=21,savefilename=None,aspect=None,
                   justcontours=False):
        """
        NAME:

           plotPotentials

        PURPOSE:

           plot a set of potentials

        INPUT:

           Pot - Potential or list of Potential instances

           rmin= minimum R (can be Quantity)

           rmax= maximum R (can be Quantity)

           nrs= grid in R

           zmin= minimum z (can be Quantity)

           zmax= maximum z (can be Quantity)

           nzs= grid in z

           phi= (None) azimuth to use for non-axisymmetric potentials

           ncontours= number of contours

           justcontours= (False) if True, just plot contours

           savefilename= save to or restore from this savefile (pickle)

        OUTPUT:

           plot to output device

        HISTORY:

           2010-07-09 - Written - Bovy (NYU)

        """
        if _APY_LOADED:
            if hasattr(Pot,'_ro'):
                tro= Pot._ro
            else:
                tro= Pot[0]._ro
            if isinstance(rmin,units.Quantity):
                rmin= rmin.to(units.kpc).value/tro
            if isinstance(rmax,units.Quantity):
                rmax= rmax.to(units.kpc).value/tro
            if isinstance(zmin,units.Quantity):
                zmin= zmin.to(units.kpc).value/tro
            if isinstance(zmax,units.Quantity):
                zmax= zmax.to(units.kpc).value/tro
        if not savefilename == None and os.path.exists(savefilename):
            print("Restoring savefile "+savefilename+" ...")
            savefile= open(savefilename,'rb')
            potRz= pickle.load(savefile)
            Rs= pickle.load(savefile)
            zs= pickle.load(savefile)
            savefile.close()
        else:
            Rs= nu.linspace(rmin,rmax,nrs)
            zs= nu.linspace(zmin,zmax,nzs)
            potRz= nu.zeros((nrs,nzs))
            for ii in range(nrs):
                for jj in range(nzs):
                    potRz[ii,jj]= evaluatePotentials(Pot,nu.fabs(Rs[ii]),
                                                     zs[jj],phi=phi,
                                                     use_physical=False)
            if not savefilename == None:
                print("Writing savefile "+savefilename+" ...")
                savefile= open(savefilename,'wb')
                pickle.dump(potRz,savefile)
                pickle.dump(Rs,savefile)
                pickle.dump(zs,savefile)
                savefile.close()
        if aspect is None:
            aspect=.75*(rmax-rmin)/(zmax-zmin)
        return plot.bovy_dens2d(potRz.T,origin='lower',cmap='gist_gray',contours=True,
                                xlabel=r"$R/R_0$",ylabel=r"$z/R_0$",
                                aspect=aspect,
                                xrange=[rmin,rmax],
                                yrange=[zmin,zmax],
                                cntrls='-',
                                justcontours=justcontours,
                                levels=nu.linspace(nu.nanmin(potRz),nu.nanmax(potRz),
                                                   ncontours))

def plotDensities(Pot,rmin=0.,rmax=1.5,nrs=21,zmin=-0.5,zmax=0.5,nzs=21,
                  phi=None,
                  ncontours=21,savefilename=None,aspect=None,log=False,
                  justcontours=False):
        """
        NAME:

           plotDensities

        PURPOSE:

           plot the density a set of potentials

        INPUT:

           Pot - Potential or list of Potential instances

           rmin= minimum R (can be Quantity)

           rmax= maximum R (can be Quantity)

           nrs= grid in R

           zmin= minimum z (can be Quantity)

           zmax= maximum z (can be Quantity)

           nzs= grid in z

           phi= (None) azimuth to use for non-axisymmetric potentials

           ncontours= number of contours

           justcontours= (False) if True, just plot contours

           savefilename= save to or restore from this savefile (pickle)

           log= if True, plot the log density

        OUTPUT:

           plot to output device

        HISTORY:

           2013-07-05 - Written - Bovy (IAS)

        """
        if _APY_LOADED:
            if hasattr(Pot,'_ro'):
                tro= Pot._ro
            else:
                tro= Pot[0]._ro
            if isinstance(rmin,units.Quantity):
                rmin= rmin.to(units.kpc).value/tro
            if isinstance(rmax,units.Quantity):
                rmax= rmax.to(units.kpc).value/tro
            if isinstance(zmin,units.Quantity):
                zmin= zmin.to(units.kpc).value/tro
            if isinstance(zmax,units.Quantity):
                zmax= zmax.to(units.kpc).value/tro
        if not savefilename == None and os.path.exists(savefilename):
            print("Restoring savefile "+savefilename+" ...")
            savefile= open(savefilename,'rb')
            potRz= pickle.load(savefile)
            Rs= pickle.load(savefile)
            zs= pickle.load(savefile)
            savefile.close()
        else:
            Rs= nu.linspace(rmin,rmax,nrs)
            zs= nu.linspace(zmin,zmax,nzs)
            potRz= nu.zeros((nrs,nzs))
            for ii in range(nrs):
                for jj in range(nzs):
                    potRz[ii,jj]= evaluateDensities(Pot,nu.fabs(Rs[ii]),
                                                    zs[jj],phi=phi,
                                                    use_physical=False)
            if not savefilename == None:
                print("Writing savefile "+savefilename+" ...")
                savefile= open(savefilename,'wb')
                pickle.dump(potRz,savefile)
                pickle.dump(Rs,savefile)
                pickle.dump(zs,savefile)
                savefile.close()
        if aspect is None:
            aspect=.75*(rmax-rmin)/(zmax-zmin)
        if log:
            potRz= nu.log(potRz)
        return plot.bovy_dens2d(potRz.T,origin='lower',cmap='gist_yarg',contours=True,
                                xlabel=r"$R/R_0$",ylabel=r"$z/R_0$",
                                aspect=aspect,
                                xrange=[rmin,rmax],
                                yrange=[zmin,zmax],
                                cntrls='-',
                                justcontours=justcontours,
                                levels=nu.linspace(nu.nanmin(potRz),nu.nanmax(potRz),
                                                   ncontours))

@potential_physical_input
@physical_conversion('frequency',pop=True)
def epifreq(Pot,R):
    """
    
    NAME:
    
        epifreq
    
    PURPOSE:
    
        calculate the epicycle frequency at R in the potential Pot
    
    INPUT:

        Pot - Potential instance or list thereof
    
        R - Galactocentric radius (can be Quantity)
    
    OUTPUT:
    
        epicycle frequency
    
    HISTORY:
    
        2012-07-25 - Written - Bovy (IAS)
    
    """
    from galpy.potential_src.planarPotential import planarPotential
    if isinstance(Pot,(Potential,planarPotential)):
        return Pot.epifreq(R,use_physical=False)
    from galpy.potential import evaluateplanarRforces, evaluateplanarR2derivs
    from galpy.potential import PotentialError
    try:
        return nu.sqrt(evaluateplanarR2derivs(Pot,R,use_physical=False)
                       -3./R*evaluateplanarRforces(Pot,R,use_physical=False))
    except PotentialError:
        from galpy.potential import RZToplanarPotential
        Pot= RZToplanarPotential(Pot)
        return nu.sqrt(evaluateplanarR2derivs(Pot,R,use_physical=False)
                       -3./R*evaluateplanarRforces(Pot,R,use_physical=False))

@potential_physical_input
@physical_conversion('frequency',pop=True)
def verticalfreq(Pot,R):
    """
    
    NAME:
    
       verticalfreq
        
    PURPOSE:
    
        calculate the vertical frequency at R in the potential Pot
    
    INPUT:

       Pot - Potential instance or list thereof
    
       R - Galactocentric radius (can be Quantity)
    
    OUTPUT:
    
        vertical frequency
    
    HISTORY:
    
        2012-07-25 - Written - Bovy (IAS@MPIA)
    
    """
    from galpy.potential_src.planarPotential import planarPotential
    if isinstance(Pot,(Potential,planarPotential)):
        return Pot.verticalfreq(R,use_physical=False)
    return nu.sqrt(evaluatez2derivs(Pot,R,0.,use_physical=False))

@potential_physical_input
@physical_conversion('dimensionless',pop=True)
def flattening(Pot,R,z):
    """
    
    NAME:
    
        flattening
    
    PURPOSE:
    
       calculate the potential flattening, defined as sqrt(fabs(z/R F_R/F_z))
    
    INPUT:

        Pot - Potential instance or list thereof
    
        R - Galactocentric radius (can be Quantity)
        
        z - height (can be Quantity)
    
    OUTPUT:
    
        flattening
    
    HISTORY:
    
        2012-09-13 - Written - Bovy (IAS)
    
    """
    return nu.sqrt(nu.fabs(z/R*evaluateRforces(Pot,R,z,use_physical=False)\
                               /evaluatezforces(Pot,R,z,use_physical=False)))

@physical_conversion('velocity',pop=True)
def vterm(Pot,l,deg=True):
    """
    
    NAME:
    
        vterm
        
    PURPOSE:
    
        calculate the terminal velocity at l in this potential

    INPUT:
    
        Pot - Potential instance
    
        l - Galactic longitude [deg/rad; can be Quantity)
        
        deg= if True (default), l in deg
        
    OUTPUT:
        
        terminal velocity
        
    HISTORY:
        
        2013-05-31 - Written - Bovy (IAS)
        
    """
    if _APY_LOADED and isinstance(l,units.Quantity):
        l= l.to(units.rad).value
        deg= False
    if deg:
        sinl= nu.sin(l/180.*nu.pi)
    else:
        sinl= nu.sin(l)
    return sinl*(omegac(Pot,sinl,use_physical=False)
                 -omegac(Pot,1.,use_physical=False))

@physical_conversion('position',pop=True)
def rl(Pot,lz):
    """
    NAME:

       rl

    PURPOSE:

       calculate the radius of a circular orbit of Lz

    INPUT:

       Pot - Potential instance or list thereof

       lz - Angular momentum (can be Quantity)

    OUTPUT:

       radius

    HISTORY:

       2012-07-30 - Written - Bovy (IAS@MPIA)

    NOTE:

       seems to take about ~0.5 ms for a Miyamoto-Nagai potential; 
       ~0.75 ms for a MWPotential

    """
    if _APY_LOADED and isinstance(lz,units.Quantity):
        if hasattr(Pot,'_ro'):
            lz= lz.to(units.km/units.s*units.kpc).value/Pot._vo/Pot._ro
        elif hasattr(Pot[0],'_ro'):
            lz= lz.to(units.km/units.s*units.kpc).value/Pot[0]._vo/Pot[0]._ro
    #Find interval
    rstart= _rlFindStart(math.fabs(lz),#assumes vo=1.
                         math.fabs(lz),
                         Pot)
    try:
        return optimize.brentq(_rlfunc,10.**-5.,rstart,
                               args=(math.fabs(lz),
                                     Pot),
                               maxiter=200,disp=False)
    except ValueError: #Probably lz small and starting lz to great
        rlower= _rlFindStart(10.**-5.,
                             math.fabs(lz),
                             Pot,lower=True)
        return optimize.brentq(_rlfunc,rlower,rstart,
                               args=(math.fabs(lz),
                                     Pot))
        

def _rlfunc(rl,lz,pot):
    """Function that gives rvc-lz"""
    thisvcirc= vcirc(pot,rl,use_physical=False)
    return rl*thisvcirc-lz

def _rlFindStart(rl,lz,pot,lower=False):
    """find a starting interval for rl"""
    rtry= 2.*rl
    while (2.*lower-1.)*_rlfunc(rtry,lz,pot) > 0.:
        if lower:
            rtry/= 2.
        else:
            rtry*= 2.
    return rtry

@physical_conversion('position',pop=True)
def lindbladR(Pot,OmegaP,m=2,**kwargs):
    """
    NAME:

       lindbladR

    PURPOSE:

       calculate the radius of a Lindblad resonance

    INPUT:

       Pot - Potential instance or list of such instances

       OmegaP - pattern speed (can be Quantity)

       m= order of the resonance (as in m(O-Op)=kappa (negative m for outer)
          use m='corotation' for corotation
       +scipy.optimize.brentq xtol,rtol,maxiter kwargs

    OUTPUT:

       radius of Linblad resonance, None if there is no resonance

    HISTORY:

       2011-10-09 - Written - Bovy (IAS)

    """
    if _APY_LOADED and isinstance(OmegaP,units.Quantity):
        if hasattr(Pot,'_ro'):
            OmegaP= OmegaP.to(1/units.Gyr).value/freq_in_Gyr(Pot._vo,Pot._ro)
        elif hasattr(Pot[0],'_ro'):
            OmegaP= OmegaP.to(1/units.Gyr).value\
                /freq_in_Gyr(Pot[0]._vo,Pot[0]._ro)
    if isinstance(m,str):
        if 'corot' in m.lower():
            corotation= True
        else:
            raise IOError("'m' input not recognized, should be an integer or 'corotation'")
    else:
        corotation= False
    if corotation:
        try:
            out= optimize.brentq(_corotationR_eq,0.0000001,1000.,
                                 args=(Pot,OmegaP),**kwargs)
        except ValueError:
            return None
        except RuntimeError: #pragma: no cover 
            raise
        return out
    else:
        try:
            out= optimize.brentq(_lindbladR_eq,0.0000001,1000.,
                                 args=(Pot,OmegaP,m),**kwargs)
        except ValueError:
            return None
        except RuntimeError: #pragma: no cover 
            raise
        return out

def _corotationR_eq(R,Pot,OmegaP):
    return omegac(Pot,R,use_physical=False)-OmegaP
def _lindbladR_eq(R,Pot,OmegaP,m):
    return m*(omegac(Pot,R,use_physical=False)-OmegaP)\
        -epifreq(Pot,R,use_physical=False)

@potential_physical_input
@physical_conversion('frequency',pop=True)
def omegac(Pot,R):
    """

    NAME:

       omegac

    PURPOSE:

       calculate the circular angular speed velocity at R in potential Pot

    INPUT:

       Pot - Potential instance or list of such instances

       R - Galactocentric radius (can be Quantity)

    OUTPUT:

       circular angular speed

    HISTORY:

       2011-10-09 - Written - Bovy (IAS)

    """
    from galpy.potential import evaluateplanarRforces
    try:
        return nu.sqrt(-evaluateplanarRforces(Pot,R,use_physical=False)/R)
    except PotentialError:
        from galpy.potential import RZToplanarPotential
        Pot= RZToplanarPotential(Pot)
        return nu.sqrt(-evaluateplanarRforces(Pot,R,use_physical=False)/R)

def nemo_accname(Pot):
    """
    NAME:
    
       nemo_accname
    
    PURPOSE:
    
       return the accname potential name for use of this potential or list of potentials with NEMO
    
    INPUT:
    
       Pot - Potential instance or list of such instances
       
    OUTPUT:
    
       Acceleration name in the correct format to give to accname=
    
    HISTORY:
    
       2014-12-18 - Written - Bovy (IAS)
    
    """
    if isinstance(Pot,list):
        out= ''
        for ii,pot in enumerate(Pot):
            if ii > 0: out+= '+'
            out+= pot.nemo_accname()
        return out
    elif isinstance(Pot,Potential):
        return Pot.nemo_accname()
    else: #pragma: no cover 
        raise PotentialError("Input to 'nemo_accname' is neither a Potential-instance or a list of such instances")
    
def nemo_accpars(Pot,vo,ro):
    """
    NAME:
    
       nemo_accpars
    
    PURPOSE:
    
       return the accpars potential parameters for use of this potential or list of potentials with NEMO
    
    INPUT:
    
       Pot - Potential instance or list of such instances

       vo - velocity unit in km/s
    
       ro - length unit in kpc
    
    OUTPUT:
    
       accpars string in the corrct format to give to accpars
    
    HISTORY:
    
       2014-12-18 - Written - Bovy (IAS)
    
    """
    if isinstance(Pot,list):
        out= ''
        for ii,pot in enumerate(Pot):
            if ii > 0: out+= '#'
            out+= pot.nemo_accpars(vo,ro)
        return out
    elif isinstance(Pot,Potential):
        return Pot.nemo_accpars(vo,ro)
    else: #pragma: no cover 
        raise PotentialError("Input to 'nemo_accpars' is neither a Potential-instance or a list of such instances")
    
def turn_physical_off(Pot):
    """
    NAME:
    
       turn_physical_off

    PURPOSE:

       turn off automatic returning of outputs in physical units

    INPUT:

       (none)

    OUTPUT:

       (none)

    HISTORY:

       2016-01-30 - Written - Bovy (UofT)

    """
    if isinstance(Pot,list):
        for pot in Pot:
            pot.turn_physical_off()
    else:
        Pot.turn_physical_off()
    return None

def turn_physical_on(Pot,ro=None,vo=None):
    """
    NAME:
       
       turn_physical_on

    PURPOSE:
    
       turn on automatic returning of outputs in physical units
    
    INPUT:
    
       ro= reference distance (kpc; can be Quantity)
       
       vo= reference velocity (km/s; can be Quantity)

    OUTPUT:
    
        (none)
    
    HISTORY:
    
        2016-01-30 - Written - Bovy (UofT)
    
    """
    if isinstance(Pot,list):
        for pot in Pot:
            pot.turn_physical_on(ro=ro,vo=vo)
    else:
        Pot.turn_physical_on(ro=ro,vo=vo)
    return None

def _check_c(Pot):
    """

    NAME:

       _check_c

    PURPOSE:

       check whether a potential or list thereof has a C implementation

    INPUT:

       Pot - Potential instance or list of such instances

    OUTPUT:

       True if a C implementation exists, False otherwise

    HISTORY:

       2014-02-17 - Written - Bovy (IAS)

    """
    if isinstance(Pot,list):
        return nu.all(nu.array([p.hasC for p in Pot],dtype='bool'))
    elif isinstance(Pot,Potential):
        return Pot.hasC

def _dim(Pot):
    """
    NAME:                                                                       
       _dim                                                                                
    PURPOSE:

       Determine the dimensionality of this potential

    INPUT:

       Pot - Potential instance or list of such instances

    OUTPUT:

       Minimum of the dimensionality of all potentials if list; otherwise Pot.dim

    HISTORY:

       2016-04-19 - Written - Bovy (UofT)
    """
    from galpy.potential import planarPotential, linearPotential
    if isinstance(Pot,list):
        return nu.amin(nu.array([p.dim for p in Pot],dtype='int'))
    elif isinstance(Pot,(Potential,planarPotential,linearPotential)):
        return Pot.dim

def _isNonAxi(Pot):
    """
    NAME:

       _isNonAxi

    PURPOSE:

       Determine whether this potential is non-axisymmetric

    INPUT:

       Pot - Potential instance or list of such instances

    OUTPUT:

       True or False depending on whether the potential is non-axisymmetric (note that some potentials might return True, even though for some parameter values they are axisymmetric)

    HISTORY:

       2016-06-16 - Written - Bovy (UofT)

    """
    isList= isinstance(Pot,list)
    if isList:
        isAxis= [not p.isNonAxi for p in Pot]
        nonAxi= not nu.prod(nu.array(isAxis))
    else:
        nonAxi= Pot.isNonAxi
    return nonAxi

def kms_to_kpcGyrDecorator(func):
    """Decorator to convert velocities from km/s to kpc/Gyr"""
    @wraps(func)
    def kms_to_kpcGyr_wrapper(*args,**kwargs):
        return func(args[0],velocity_in_kpcGyr(args[1],1.),args[2],**kwargs)
    return kms_to_kpcGyr_wrapper
