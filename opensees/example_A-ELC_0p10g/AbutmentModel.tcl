# AbutmentModel.tcl --
#
#        Abutment Model (called from the Abutment.tcl file).
#
#            MSBridge (Beta 1.0.1.20324)
#        OpenSees Analysis of Multi-Span Bridges
#      Copyright (c) 2019 All Rights Reserved.
#
# Units: kN, m
# 1) 8/26/2010, original code by Kevin Mackie (kmackie@mail.ucf.edu)
# 2) 9/25/2012, added distributed springs and skew angle by Ning Wang
# 3) 7/17/2013, updated for curve bridges by Jinchi Lu
#
#
# Transverse arrays created at abutments and springs inserted in series
# and parallel to simulate gapping, embankment, shear keys, bearing
# pads, etc.
#
# 2010/08/16 - fixed a problem where I (Kevin) forgot Jinchi is using Z as vertical
# 2010/08/26 - added correct regions for Jinchi to record element forces
#
# INPUT for constructor routine:
#	1.	<massa> lumped mass from embankment soil and structural weight of abutment ()
#	2.	<Vsoil> embankment soil shear wave velocity (m/s)
#	3.	<sden> embankment soil density (kg/m3)
#	4.	<Slp> embankment slope (dimensionless)
#	5.	<skew> skew angle (degree)
#	6.	<elastic> 0 = default nonlinear, 1 = elastic analysis
#	7.	<threeD> 1 = for 3D analysis, 0 for 2D
#	8.	<coordTransf> geometric transformation tag for deck elements
#	9.	<fy> steel yield strength (kPa)
#	10.	<fc> concrete compressive strength (kPa)
#	11.	<mDenConc> concrete unit weight (kN/m3)
#	12.	<mDenSteel> steel unit weight (kN/m3)
#	13.	<deckNode> node connecting to deck
#	14.	<abutNode> node connecting to diagonal abutment member
#	15.	<ornt> -1 if compression is in the global -X, 1 if compression is in the global +X
#	16.	<gap> longitudinal gap (m)
#	17.	<dead_load> dead load at abutment from superstructure (kN)
#	18.	<dw> deck width at abutment (m)
#	19.	<dd> deck depth at abutment (m)
#	20.	<Ht> height including distance to deck center of mass, used for embankment height ==Hcol in MSBridgr (m)
#
# INPUT for recorder routine:
#
# INPUT for post_static routine:

package provide SDC2010SandAbutment 1.1.3

namespace eval ::SDC2010SandAbutment:: {
    variable AbutInfo
    # Export public commands
    namespace export SDC2010SandAbutment
}

proc ::SDC2010SandAbutment::SDC2010SandAbutment {name tag shift abutArgs} {
	# define SDC2010SandAbutment namespace variables
    variable AbutInfo
    
	variable g 9.81
	variable pi [expr acos(-1.0)]
	
	# lumped mass at abutment should take into account structural concrete weight
	# as well as some participating soil mass
	#variable massa 150.0
	
	# Vsoil in m/s, sden in kg/m^3, slope is dimensionless
	#variable Vsoil 150.0
	#variable sden 1760.6
	#variable Slp 2.0
	#variable totalb 2.0
	#variable skew 0.0

    # FIRST, qualify the name.
    if {![string match "::*" $name]} {
        # Get caller's namespace; #
        # append :: if not global namespace.
        set ns [uplevel 1 namespace current]
        if {"::" != $ns} {
            append ns "::"
        }
        
        set name "$ns$name"
    }

    # NEXT, Check the name
    if {"" != [info command $name]} {
        #return -code error  "object name "$name" already exists"
        puts "SDC2010SandAbutment warning: object name "$name" already exists"
    }
    
	# define tags
	set AbutInfo($name-tag) $tag
	set AbutInfo($name-shift) $shift
	set AbutInfo($name-matNum) $shift
	set AbutInfo($name-eleNum) $shift
	set AbutInfo($name-nodeNum) $shift

	# Now parse data from abutArgs
	if { [info tclversion] > 8.4 } {
       # Tcl 8.5 is not installed on MP computer
		lassign  $abutArgs  \
			massa Vsoil sden Slp skew Ki Pabut abutKfactor\
			elastic threeD coordTransf fy fc mDenConc mDenSteel \
		deckNode abutNode ornt gap dead_load dw dd Ht NSpr
    } else {
		set massa [lindex $abutArgs 0]
		set Vsoil [lindex $abutArgs 1]
		set sden [lindex $abutArgs 2]
		set Slp [lindex $abutArgs 3]
		set skew [lindex $abutArgs 4]
		set Ki [lindex $abutArgs 5]
		set Pabut [lindex $abutArgs 6]
		set abutKfactor [lindex $abutArgs 7]
		set elastic [lindex $abutArgs 8]
		set threeD [lindex $abutArgs 9]
		set coordTransf [lindex $abutArgs 10]
		set fy [lindex $abutArgs 11]
		set fc [lindex $abutArgs 12]
		set mDenConc [lindex $abutArgs 13]
		set mDenSteel [lindex $abutArgs 14]
		set deckNode [lindex $abutArgs 15]
		set abutNode [lindex $abutArgs 16]
		set ornt [lindex $abutArgs 17]
		set gap [lindex $abutArgs 18]
		set dead_load [lindex $abutArgs 19]
		set dw [lindex $abutArgs 20]
		set dd [lindex $abutArgs 21]
		set Ht [lindex $abutArgs 22]
    		set NSpr [lindex $abutArgs 23]
	}
    	
    # NEXT, Save the data
	set AbutInfo($name-massa) $massa
 	set AbutInfo($name-Vsoil) $Vsoil
    set AbutInfo($name-sden) $sden
    set AbutInfo($name-Slp) $Slp
    set AbutInfo($name-skew) $skew
    set AbutInfo($name-Ki) $Ki
    set AbutInfo($name-Pabut) $Pabut
    set AbutInfo($name-abutKfactor) $abutKfactor
    
    set AbutInfo($name-elastic) $elastic
    set AbutInfo($name-threeD) $threeD
    set AbutInfo($name-dTransf) $coordTransf
    set AbutInfo($name-fy) $fy
    set AbutInfo($name-fc) $fc
    set AbutInfo($name-mDenConc) $mDenConc
    set AbutInfo($name-mDenSteel) $mDenSteel
    
    set AbutInfo($name-deckNode) $deckNode
    set AbutInfo($name-abutNode) $abutNode
    set AbutInfo($name-ornt) $ornt
    set AbutInfo($name-gap) $gap
    set AbutInfo($name-dead_load) $dead_load
    set AbutInfo($name-dw) $dw
    set AbutInfo($name-dd) $dd
    set AbutInfo($name-Ht) $Ht
    set AbutInfo($name-NSpr) $NSpr
    # for PEER-Br, some options not supported
    if { $AbutInfo($name-threeD) == 0 } {
        error "SDC2010SandAbutment does not support threeD = 0 for PEER-Br"
    }
    if { $AbutInfo($name-elastic) == 1 } {
        error "SDC2010SandAbutment does not support elastic = 1 for PEER-Br"
    }
    
    # NEXT, Create the object.
    proc $name {method args}  "::SDC2010SandAbutment::SDC2010SandAbutmentMethods $name \$method \$args"
    
    return $name
}

proc ::SDC2010SandAbutment::SDC2010SandAbutmentMethods {name method argList} {
    variable AbutInfo
    switch -exact -- $method {
        information -
        initialize -
        recorder -
        post_static -
        post_dynamic {
            if {[catch "Op_$method $name $argList"  result]} {
                regsub -- "Op_$method" $result  "$name $method" result
                return -code error $result
            } else {
                return $result
            }
        }
        default {
            return -code error  ""$name $method" is not defined"
        }
    }
}

proc ::SDC2010SandAbutment::Op_initialize {name} {
	# actually creates the materials, nodes, elements, etc
	variable AbutInfo
	variable pi; variable g

	# unit conversions
	set ksi_kPa 6894.76
	set kip_kN 4.4482
	set in_m 0.0254
   set m_ft [expr 1/$in_m/12]
	set in2_m2 [expr $in_m*$in_m]
	set kli_kNlm [expr $kip_kN/$in_m]
	
	set doRayleigh 1; # 0 -- no Rayleigh damping for zeroLength (abutment only); 1 - consider Rayleigh
	
	set numOfActualBearings 3; # 0 -- no bearing; 2 or larger (cannot be 1)
  if { $numOfActualBearings == 0 } {
      set nbearing 2;
  } else {
      set nbearing $numOfActualBearings;
  }
	
	set bearingHt [expr 2*$in_m]
	# approximate width of back wall and wing wall (ww is about 1/2-1/3 of bw length)
   set ft 12.0
    set wbw [expr 27*$ft*$in_m]
    set hbw [expr 6*$ft*$in_m]
    set www [expr $AbutInfo($name-dw)/3.0]
    set www [expr 13*$ft*$in_m]; # about $AbutInfo($name-dw)/3.0
    # longitudinal abutment response properties from Caltrans SDC

   # adjust abutment stiffness for Equivalent Static Analysis
	set AbutInfo($name-Ki) [expr $AbutInfo($name-Ki)*$AbutInfo($name-abutKfactor)]
    #set kabl [expr $AbutInfo($name-Ki)*$wbw*($AbutInfo($name-dd)/1.6764)]
    #set pbwl [expr $AbutInfo($name-Pabut)*$wbw*$AbutInfo($name-dd)*($AbutInfo($name-dd)/1.6764)]
    set kabl [expr $AbutInfo($name-Ki)*$wbw*$hbw/1.6764]
    set pbwl [expr $AbutInfo($name-Pabut)*$wbw*$hbw*$hbw/1.6764]
    # transverse abutment response properties from Caltrans SDC
	set CW [expr 4.0/3.0]
	set CL [expr 2.0/3.0]
	set CWL 0.9
    #set kabt [expr $AbutInfo($name-Ki)*$www*($AbutInfo($name-dd)/1.6764)*$CWL]
    #set pbwt [expr $AbutInfo($name-Pabut)*$www*$AbutInfo($name-dd)*($AbutInfo($name-dd)/1.6764)*$CWL]
    set kabt [expr $AbutInfo($name-Ki)*$www*$hbw/1.6764*$CWL]
    set pbwt [expr $AbutInfo($name-Pabut)*$www*$hbw*$hbw/1.6764*$CWL]
	# bearing pads, EPP materials with small amount of kinematic hardening ----------------------------
	
	# elastomeric properties
	set Gbp [expr 0.15*$ksi_kPa]
	set Ebp [expr 5*$ksi_kPa]
	
	# pad dimensions.  Use less than the seat width for the horizontal dimension (assume square)
	#set hbp [expr 2.0*$in_m]
	set hbp [expr $bearingHt]
	set dimbp [expr 20*$in_m]
	set Abp [expr $dimbp*$dimbp]
	
	# assume yield at 150% shear strain, ultimate at 300% shear strain
	set uybp [expr 1.5*$hbp]
	set kbp [expr $Gbp*$Abp/$hbp]
	set fybp [expr $kbp*$uybp]
	
	# vertical bp response
	set fyt [expr 2.25*$ksi_kPa]
	set fvbp [expr $fyt*$Abp]
	set kvbp [expr $Ebp*$Abp/$hbp]
   set vgap [expr 2*$in_m]

  if { $numOfActualBearings == 0 } {
	    uniaxialMaterial Elastic		[expr $AbutInfo($name-matNum)+1]   1.0e-10
  } else {
	    uniaxialMaterial Steel01		[expr $AbutInfo($name-matNum)+1]   $fybp  $kbp   0
  }

	# vertical response of the embankment -------------------------------------------------------------
	set cfactor [expr 1.0/$AbutInfo($name-NSpr)]
	set Gsl [expr $AbutInfo($name-sden)*pow($AbutInfo($name-Vsoil),2)]
	set zo [expr 0.5*$AbutInfo($name-dw)*$AbutInfo($name-Slp)]
	set Esl [expr 2.0*1.4*$Gsl]
	set kvu [expr ($Esl*$AbutInfo($name-dw))/($zo*log(($zo+$AbutInfo($name-Ht))/$zo))]
	set Lc [expr (0.7*pow($AbutInfo($name-Slp)*$AbutInfo($name-Ht)*$AbutInfo($name-dw),0.5))]
	set kv [expr $kvu*$Lc]
	set kv [expr 9.47948e+006*$kli_kNlm]
	uniaxialMaterial Elastic       [expr $AbutInfo($name-matNum)+23]   [expr $kv*$cfactor]
  if { $numOfActualBearings == 0 } {
	    uniaxialMaterial Elastic		[expr $AbutInfo($name-matNum)+2]   [expr $kv*$cfactor]
  } else {
	    uniaxialMaterial Steel01		[expr $AbutInfo($name-matNum)+2]   $fvbp  $kvbp  1.0e-2      
  }

	# combine vertical bearing pad and stiff spring for bearing on stem wall
	#uniaxialMaterial ElasticPPGap	[expr $AbutInfo($name-matNum)+3]   [expr $kv*2.0]  [expr -$kv*2.0*2.0]  -$hbp  damage
	uniaxialMaterial ElasticPPGap	[expr $AbutInfo($name-matNum)+3]   1.0e10  -1.0e10  -$hbp  damage
	#uniaxialMaterial ElasticPPGap	[expr $AbutInfo($name-matNum)+3]   1.0e10  -1.0e10  -$vgap  damage
	uniaxialMaterial Parallel		[expr $AbutInfo($name-matNum)+4]   [expr $AbutInfo($name-matNum)+2] [expr $AbutInfo($name-matNum)+3]
	# stiff elastic spring if needed
	#uniaxialMaterial Elastic       [expr $AbutInfo($name-matNum)+29]   1.0e10

	# shear keys (compression only material but on both sides of deck) --------------------------------
	
	# initial elastic stiffness from series stiffness of cantilever shear and flexural portions
	# this assumes some effective rectangular shape of the external shear key
	# hardening and softening stiffness assumed 2.5% of initial
	set kel [expr 17000*$kli_kNlm]
	set kgp [expr 0*$in_m]
	set kskh [expr 0.025*$kel]
	set ksks [expr 0.025*$kel]
	
	# ultimate capacity comes from 30 percent of dead load at abutment
	set fusk [expr 0.3*$AbutInfo($name-dead_load)]
	set fysk [expr $fusk*2.0/3.0]
	set kia $kel
	set kha $kskh
	set u1a [expr $fysk/$kia+$kgp]
	set u2a [expr $u1a+($fusk-$fysk)/$kha]
	set flsk [expr 0.02*$fysk]
	uniaxialMaterial ElasticMultiLinear  [expr $AbutInfo($name-matNum)+6] -strain  [expr -($u2a+10.0*($u2a-$u1a))] -$u2a -$u1a  0.0 $u1a $u2a [expr $u2a+10.0*($u2a-$u1a)] \
		   -stress -$flsk -$fusk -$fysk 0.0 $fysk $fusk $flsk
	#uniaxialMaterial MinMax  	         [expr $AbutInfo($name-matNum)+6]   [expr $AbutInfo($name-shift)+5]  -min [expr -($fusk-$fysk)/$kskh] \
	#        -max [expr ($fusk-$fysk)/$kskh]
	  
	
	# longitudinal backwall and fill response ---------------------------------------------------------
	# (includes pile effect if model takes this into account)
	# cfactor should be 1/n if n springs are used, 1 if only 1 spring is used
	set cfactor [expr 1.0/$AbutInfo($name-NSpr)] 
	#uniaxialMaterial ElasticPPGap     [expr $AbutInfo($name-matNum)+39]  [expr $kabl*$cfactor]  [expr $pbwl*$cfactor]  0  damage
	#uniaxialMaterial ElasticPPGap     [expr $AbutInfo($name-matNum)+40]  [expr $kabl*$cfactor]  [expr -$pbwl*$cfactor]  0  damage     
	uniaxialMaterial Steel01       [expr $AbutInfo($name-matNum)+41]  [expr $pbwl*$cfactor]  [expr  $kabl*$cfactor] 1.0e-2		
	# create additional gap material for impact with backwall
	uniaxialMaterial ElasticPPGap       [expr $AbutInfo($name-matNum)+37]  1.0e10  -1.0e10   -$AbutInfo($name-gap)   damage
	uniaxialMaterial Parallel	   [expr $AbutInfo($name-matNum)+36]	[expr $AbutInfo($name-matNum)+1]  [expr  $AbutInfo($name-matNum)+37]
	# transverse wingwall/fill response ---------------------------------------------------------------
	set cfactor 0.5
	uniaxialMaterial Steel01     [expr $AbutInfo($name-matNum)+38]  [expr $pbwt*$cfactor]  [expr $kabt*$cfactor]  1.0e-2
	# combine bearing pad and shear key for transverse direction
	uniaxialMaterial Parallel      [expr $AbutInfo($name-matNum)+26]   [expr $AbutInfo($name-matNum)+6] [expr $AbutInfo($name-matNum)+1]
   
	# coordinates of deck connector node
	# note, Jinchi is using Z as vertical, so we need to switch these with our previous vertical Y
	set xi [nodeCoord $AbutInfo($name-deckNode) 1]
   set yi [nodeCoord $AbutInfo($name-deckNode) 3]
   set zi [nodeCoord $AbutInfo($name-deckNode) 2]
	 	
   puts " xi = $xi  yi = $yi  zi = $zi " 
   set leftAbutCurveAngle 0
   set rightAbutCurveAngle 0
	if { $AbutInfo($name-ornt) < 0 } {; # left abutment
		set sinskew [expr sin(($AbutInfo($name-skew)+$leftAbutCurveAngle)*$pi/180.0)]
		set cosskew [expr cos(($AbutInfo($name-skew)+$leftAbutCurveAngle)*$pi/180.0)]
		set sinabut [expr sin(-$leftAbutCurveAngle*$pi/180.0)]
		set cosabut [expr cos(-$leftAbutCurveAngle*$pi/180.0)]
	} else {; # right aboutment
		set sinskew [expr sin(($AbutInfo($name-skew)+$rightAbutCurveAngle)*$pi/180.0)]
		set cosskew [expr cos(($AbutInfo($name-skew)+$rightAbutCurveAngle)*$pi/180.0)]
		set sinabut [expr sin(-$rightAbutCurveAngle*$pi/180.0)]
		set cosabut [expr cos(-$rightAbutCurveAngle*$pi/180.0)]
	}	
	set sinskew_rabut [expr sin($rightAbutCurveAngle*$pi/180.0)]
	set cosskew_rabut [expr cos($rightAbutCurveAngle*$pi/180.0)]
	 	
	set distributedSpringDir "[expr $AbutInfo($name-ornt)*-1*$cosskew] [expr $AbutInfo($name-ornt)*-1*$sinskew] 0  $sinskew [expr -1*$cosskew] 0"
	set distributedSpringDir2 "[expr $AbutInfo($name-ornt)*-1*$cosskew] [expr $AbutInfo($name-ornt)*-1*$sinskew] 0  [expr -1*$sinskew] [expr 1*$cosskew] 0"
	if { $AbutInfo($name-ornt) < 0 } {; # left abutment
		set abutDir "[expr $AbutInfo($name-ornt)*-1] 0 0  0 [expr $AbutInfo($name-ornt)*-1] 0"
		set abutmentModelNodeCoor "abutmentModelNodeCoorL.txt"
	 	
	} else {; # right aboutment
		set abutmentModelNodeCoor "abutmentModelNodeCoorR.txt"
		set abutDir "[expr $AbutInfo($name-ornt)*-1*$cosskew_rabut] [expr $AbutInfo($name-ornt)*-1*$sinskew_rabut] 0  $sinskew_rabut [expr -1*$cosskew_rabut] 0"
	}	
		set fabut [open "$abutmentModelNodeCoor" "w"]
	 	
	# Define transverse arrays of elements at the abutments
	set totalb [expr $nbearing-1.0]
	set incrt [expr $AbutInfo($name-dw)/($totalb+2.0)]
	set temp [expr ($totalb/2.0)-int(floor($totalb/2.0))]
	set interNSpr [expr $AbutInfo($name-NSpr)-2]
	# Define transverse arrays of elements at the abutments
	set totalb2 [expr $interNSpr-1.0]
	set incrt2 [expr $AbutInfo($name-dw)/($totalb2+2.0)]
	set temp2 [expr ($totalb2/2.0)-int(floor($totalb2/2.0))]
	if { $temp == 0 } {
		# For an even number of boxes
		for {set nb 1} {$nb <= [expr int(($totalb+2.0)/2.0)]} {incr nb} {
			set z($nb) [expr $incrt*$nb]
			set x($nb) [expr $incrt*$nb*tan($AbutInfo($name-skew)*$pi/180.0)]
		}
	} elseif { $temp > 0 } {  
		# For an odd number of boxes
		set z1 [expr 0.5*$incrt]
		set x1 [expr 0.5*$incrt*tan($AbutInfo($name-skew)*$pi/180.0)]
		
		for {set nb 2} {$nb <= [expr int(($totalb+3.0)/2.0)]} {incr nb} {
			set z($nb) [expr (0.5*$incrt+$incrt*($nb-1.0))]
			set x($nb) [expr (0.5*$incrt+$incrt*($nb-1.0))*tan($AbutInfo($name-skew)*$pi/180.0)]
		}
	}

	if { $temp == 0 } {
		# For an even number of boxes  

		set nb [expr int(($totalb+2.0)/2.0)]
		node [expr $AbutInfo($name-nodeNum)+0]  $xi  $zi  $yi  -mass $AbutInfo($name-massa) $AbutInfo($name-massa) $AbutInfo($name-massa) 0.0 0.0 0.0
		
		for {set nn 1} {$nn <= [expr int($nb)]} {incr nn} { 
			set xx [expr -$x($nn)]
			set zz [expr  $z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+$nn]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr  $x($nn)]
			set zz [expr -$z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int($nn+$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr -$x($nn)]
			set zz [expr  $z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int($nn+4.0*$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr  $x($nn)]
			set zz [expr -$z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int($nn+5.0*$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
		}  

		# deck array	
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+1] [expr $AbutInfo($name-nodeNum)+1] $AbutInfo($name-deckNode) \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nb+1.0)] $AbutInfo($name-deckNode) [expr $AbutInfo($name-nodeNum)+int($nb+1.0)] \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
							
		for {set nn 1} {$nn <= [expr int($nb-1.0)]} {incr nn} { 
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nn+1.0)] [expr $AbutInfo($name-nodeNum)+int($nn+1.0)] [expr $AbutInfo($name-nodeNum)+$nn] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int($nb+$nn)] [expr $AbutInfo($name-nodeNum)+int($nb+$nn+1.0)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		}
		
		# abutment array
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(4.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+0] \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(5.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+0]  [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+1.0)] \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		for {set nn 1} {$nn <= [expr int($nb-1.0)]} {incr nn} { 
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(4.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(5.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn+1.0)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		}

		# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
		eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(8.0*$nb)]  [expr $AbutInfo($name-nodeNum)+0] $AbutInfo($name-deckNode)        -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+26] [expr $AbutInfo($name-matNum)+4] \
			-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
		fix [expr $AbutInfo($name-nodeNum)+0]  0 0 0 0 1 0

		for {set nn 1} {$nn <= [expr int($nb-1.0)]} {incr nn} { 
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(8.0*$nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn)] [expr $AbutInfo($name-nodeNum)+$nn]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1] [expr $AbutInfo($name-matNum)+4]  \
				-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(9.0*$nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn)] [expr $AbutInfo($name-nodeNum)+int($nb+$nn)]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1]  [expr $AbutInfo($name-matNum)+4]  \
				-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
		}
		if { $temp2 == 0 } {
			# For an even number of boxes
			for {set nsp 1} {$nsp <= [expr int(($totalb2+2.0)/2.0)]} {incr nsp} {
				set z($nsp) [expr $incrt2*$nsp]
				set x($nsp) [expr $z($nsp)*tan($AbutInfo($name-skew)*$pi/180.0)]
			}
		} elseif { $temp2 > 0 } {  
			# For an odd number of boxes
			set z(1) [expr 0.5*$incrt2]
			set x(1) [expr $z(1)*tan($AbutInfo($name-skew)*$pi/180.0)]
			for {set nsp 2} {$nsp <= [expr int(($totalb2+3.0)/2.0)]} {incr nsp} {
				set z($nsp) [expr ($z(1)+$incrt2*($nsp-1.0))]
				set x($nsp) [expr $z($nsp)*tan($AbutInfo($name-skew)*$pi/180.0)]
			}
		}
		
		# node
		if { $temp2 == 0 } {
			# For an even number of boxes  
			set nb2 [expr int(($totalb2+2.0)/2.0)]
			node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)]  $xi  $zi  $yi
			#fix	[expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] 1 1 1 1 1 1
			if { [llength $AbutInfo($name-abutNode)] == 1 } {
				equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)]  1 2 3 4 5 6
			}		
			for {set nn 1} {$nn <= [expr int($nb2)]} {incr nn} { 
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  [expr  $xx1+$xi]  [expr $zz1+$zi]  $yi	
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  [expr  $xx1+$xi]  [expr $zz1+$zi]  $yi
				if { [llength $AbutInfo($name-abutNode)] == 2 } {
					if {$nn<int($nb2)} {
						#fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 1 1 1 1 1
						#fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 1 1 1 1 1
						#	puts "fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 1 1 1 1 1"
						#	puts "fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 1 1 1 1 1"
					} else {
						equalDOF [expr $AbutInfo($name-nodeNum)+int(5.0*$nb)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  1 2 3 4 5 6
						equalDOF [expr $AbutInfo($name-nodeNum)+int(6.0*$nb)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  1 2 3 4 5 6					
						if { [llength $AbutInfo($name-abutNode)] == 2 } {
							equalDOF [lindex $AbutInfo($name-abutNode) 0] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 2 3 4 5 6
							equalDOF [lindex $AbutInfo($name-abutNode) 1] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 2 3 4 5 6
						} 
							if { [llength $AbutInfo($name-abutNode)] == 2 } {
							}		
						}		
				#} else {
				#	error "SDC2010SandAbutment requires either 1 or 2 abutNodes as input"
				}			
			}  
		
			# abutment array	
			if { $nb2 >= 1 } {
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb)] [expr $AbutInfo($name-nodeNum)+0] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1.0+1.0*$nb2)] [expr $AbutInfo($name-nodeNum)+0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+1.0*$nb2+1)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+$nb2+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb+5.0*$nb2)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn+1)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			}
			
			# springs connecting the abutment array to fixity
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			global deckSpringArrayEles
			set deckSpringArrayEles {}
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+0] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2)]				
			if { [llength $AbutInfo($name-abutNode)] == 1 } {
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+1)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+0] -mat  [expr $AbutInfo($name-matNum)+38]  \
				-dir  2 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+1)]				
			}
			if { $nb2 >= 1 } {
			for {set nn 1} {$nn <= [expr int($nb2-1)]} {incr nn} { 
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  -mat   [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"  
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  -mat   [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"  
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]
			}		
			}		

			if { $nb2 >= 1 } {
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"  
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 

			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]

			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+38] \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+38]  \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"

			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]
			}		

			# define regions for possible increased abutment damping, should include all elements
			region [expr $AbutInfo($name-shift)+0] -ele $deckSpringArrayEles
			# define regions for bearing pad and longitudinal recorders
			region [expr $AbutInfo($name-shift)+2] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb+1.0)] \
				[expr $AbutInfo($name-eleNum)+int(9.0*$nb+1.0)] [expr $AbutInfo($name-eleNum)+int(10.0*$nb)] \
				[expr $AbutInfo($name-eleNum)+int(10.0*$nb+1.0)]
			# define regions for transverse shear key recorders
			region [expr $AbutInfo($name-shift)+3] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb)]

		} elseif { $temp2 > 0 } {
			# For an odd number of boxes
			set nb2 [expr int(($totalb2+3.0)/2.0)]
			for {set nn 1} {$nn <= [expr int($nb2)]} {incr nn} {
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				if { [llength $AbutInfo($name-abutNode)] == 2 || [llength $AbutInfo($name-abutNode)] == 1 } {
					if {$nn<int($nb2)} {
						#fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  1 1 1 1 1 1
						#fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  1 1 1 1 1 1
						#	puts "fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  1 1 1 1 1 1"
						#	puts "fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  1 1 1 1 1 1"
					} elseif {$nn==int($nb2)} {		
						equalDOF [expr $AbutInfo($name-nodeNum)+int(5.0*$nb)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)]  1 2 3 4 5 6
						equalDOF [expr $AbutInfo($name-nodeNum)+int(6.0*$nb)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)]  1 2 3 4 5 6					
						if { [llength $AbutInfo($name-abutNode)] == 2 } {
							equalDOF [lindex $AbutInfo($name-abutNode) 0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)]  1 2 3 4 5 6
							equalDOF [lindex $AbutInfo($name-abutNode) 1] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  1 2 3 4 5 6
						} else {
							equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)]  1 2 3 4 5 6
							equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  1 2 3 4 5 6
						}		
							if { [llength $AbutInfo($name-abutNode)] == 2 } {
							} else {
							}		
						}		
				} else {
					error "SDC2010SandAbutment requires either 1 or 2 abutNodes as input"
				}
			} 

			# deck array 
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+0]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nb2+1.0)]  [expr $AbutInfo($name-nodeNum)+0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+1.0)]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			if { $nb2 >= 1 } {
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} {
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nb2+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn+1.0)]  \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			}	
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+1)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			# springs connecting the deck array to the abutment array
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			global deckSpringArrayEles
			set deckSpringArrayEles {}	
			if { $nb2 >= 1 } {
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} {
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)]  -mat [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]
			}
			}
			
			# springs connecting the abutment array to fixity
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)] 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  

			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+38] \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+38] \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)] 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  

			# define regions for possible increased abutment damping, should include all elements
			region [expr $AbutInfo($name-shift)+0] -ele $deckSpringArrayEles
													
		}
		
			

	} elseif { $temp > 0 } {
		# For an odd number of boxes
		set nb [expr int(($totalb+3.0)/2.0)]
		node [expr $AbutInfo($name-nodeNum)+0]   $xi  $zi  $yi  -mass $AbutInfo($name-massa) $AbutInfo($name-massa) $AbutInfo($name-massa) 0.0 0.0 0.0

			set xx [expr -$x1]
			set zz [expr  $z1]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+1]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr  $x1]
			set zz [expr -$z1]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int($nb+1)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr -$x1]
			set zz [expr  $z1]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int(4.0*$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr  $x1]
			set zz [expr -$z1]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+1.0)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
		for {set nn 2} {$nn <= [expr int($nb)]} {incr nn} {
			set xx [expr -$x($nn)]
			set zz [expr  $z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+$nn]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr  $x($nn)]
			set zz [expr -$z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int($nn+$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
			set xx [expr -$x($nn)]
			set zz [expr  $z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn-1.0)]  [expr $xx1+$xi] [expr $zz1+$zi]  $yi
			set xx [expr  $x($nn)]
			set zz [expr -$z($nn)]
			set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
			set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
			node [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn)] [expr $xx1+$xi] [expr $zz1+$zi]  $yi
		}             
		
		# deck array
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+1]  [expr $AbutInfo($name-nodeNum)+1]  $AbutInfo($name-deckNode)  \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nb+1.0)]  $AbutInfo($name-deckNode) [expr $AbutInfo($name-nodeNum)+int($nb+1.0)]  \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		
		for {set nn 1} {$nn <= [expr int($nb-1.0)]} {incr nn} {
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nn+1.0)] [expr $AbutInfo($name-nodeNum)+int($nn+1.0)] [expr $AbutInfo($name-nodeNum)+$nn]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int($nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int($nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int($nb+$nn+1.0)]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		}
					
		# abutment array
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(4.0*$nb)]  [expr $AbutInfo($name-nodeNum)+int(4.0*$nb)] [expr $AbutInfo($name-nodeNum)+0]  \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(5.0*$nb+1.0)]  [expr $AbutInfo($name-nodeNum)+0] [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+1.0)]  \
			10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		for {set nn 2} {$nn <= [expr int($nb)]} {incr nn} {
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(4.0*$nb+$nn-1.0)] [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn-1.0)] [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn-2.0)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(5.0*$nb+$nn)] [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn-1.0)]  [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn)]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
		}
		
		# springs connecting the deck array to the abutment array
		# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
		eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(8.0*$nb+1.0)]  [expr $AbutInfo($name-nodeNum)+int(4.0*$nb)] [expr $AbutInfo($name-nodeNum)+1]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1] [expr $AbutInfo($name-matNum)+4] \
			-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
		eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(8.0*$nb)]  [expr $AbutInfo($name-nodeNum)+0] $AbutInfo($name-deckNode)        -mat  [expr $AbutInfo($name-matNum)+6] \
			-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
		eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(9.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+int($nb+1.0)]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1] [expr $AbutInfo($name-matNum)+4]  \
			-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
				
		fix [expr $AbutInfo($name-nodeNum)+0]  0 0 0 0 1 0
				
		
		for {set nn 2} {$nn <= [expr int($nb-1.0)]} {incr nn} {
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(8.0*$nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int(4.0*$nb+$nn-1.0)] [expr $AbutInfo($name-nodeNum)+$nn]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1] [expr $AbutInfo($name-matNum)+4]  \
				-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(9.0*$nb+$nn)]  [expr $AbutInfo($name-nodeNum)+int(5.0*$nb+$nn)] [expr $AbutInfo($name-nodeNum)+int($nb+$nn)]  -mat  [expr $AbutInfo($name-matNum)+36] [expr $AbutInfo($name-matNum)+1] [expr $AbutInfo($name-matNum)+4]  \
				-dir  1 2 3 -doRayleigh $doRayleigh -orient  $abutDir"
		}
		
		global deckSpringArrayEles
		set deckSpringArrayEles {}
		lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(11.0*$nb)]
		lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(11.0*$nb+1.0)]

		
		# define regions for possible increased abutment damping, should include all elements
		region [expr $AbutInfo($name-shift)+0] -ele [expr $AbutInfo($name-eleNum)+int(11.0*$nb)] [expr $AbutInfo($name-eleNum)+int(11.0*$nb+1.0)]
		region [expr $AbutInfo($name-shift)+1] -node [expr $AbutInfo($name-nodeNum)+int(5.0*$nb-1.0)] [expr $AbutInfo($name-nodeNum)+int(6*$nb)]
		# define regions for bearing pad and longitudinal recorders
		region [expr $AbutInfo($name-shift)+2] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb+1.0)] \n			[expr $AbutInfo($name-eleNum)+int(9.0*$nb+1.0)] [expr $AbutInfo($name-eleNum)+int(11.0*$nb)] \n			[expr $AbutInfo($name-eleNum)+int(11.0*$nb+1.0)]
		# define regions for transverse shear key recorders
		region [expr $AbutInfo($name-shift)+3] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb)]
		if { $temp2 == 0 } {
			# For an even number of boxes
			for {set nsp 1} {$nsp <= [expr int(($totalb2+2.0)/2.0)]} {incr nsp} {
				set z($nsp) [expr $incrt2*$nsp]
				set x($nsp) [expr $z($nsp)*tan($AbutInfo($name-skew)*$pi/180.0)]
			}
		} elseif { $temp2 > 0 } {  
			# For an odd number of boxes
			set z(1) [expr 0.5*$incrt2]
			set x(1) [expr $z(1)*tan($AbutInfo($name-skew)*$pi/180.0)]
			for {set nsp 2} {$nsp <= [expr int(($totalb2+3.0)/2.0)]} {incr nsp} {
				set z($nsp) [expr ($z(1)+$incrt2*($nsp-1.0))]
				set x($nsp) [expr $z($nsp)*tan($AbutInfo($name-skew)*$pi/180.0)]
			}
		}
		
		# node
		if { $temp2 == 0 } {
			# For an even number of boxes  
			set nb2 [expr int(($totalb2+2.0)/2.0)]
			node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)]  $xi  $zi  $yi
			#fix	[expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] 1 1 1 1 1 1
			for {set nn 1} {$nn <= [expr int($nb2)]} {incr nn} { 
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				if { [llength $AbutInfo($name-abutNode)] == 2 || [llength $AbutInfo($name-abutNode)] == 1 } {
					if {$nn<int($nb2)} {
						#fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 1 1 1 1 1
						#fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 1 1 1 1 1
							#puts "fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 1 1 1 1 1"
							#puts "fix [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 1 1 1 1 1"
					} else {
						equalDOF [expr $AbutInfo($name-nodeNum)+int(5.0*$nb-1)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  1 2 3 4 5 6
						equalDOF [expr $AbutInfo($name-nodeNum)+int(6.0*$nb)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  1 2 3 4 5 6					
						if { [llength $AbutInfo($name-abutNode)] == 2 } {
							equalDOF [lindex $AbutInfo($name-abutNode) 0] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 2 3 4 5 6
							equalDOF [lindex $AbutInfo($name-abutNode) 1] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 2 3 4 5 6
						} else {
							equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)]  1 2 3 4 5 6
							equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)]  1 2 3 4 5 6
						}		
							if { [llength $AbutInfo($name-abutNode)] == 2 } {
							} else {
							}		
					}		
				} else {
					error "SDC2010SandAbutment requires either 1 or 2 abutNodes as input"
				}			
			}  
		
			# abutment array	
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb)] [expr $AbutInfo($name-nodeNum)+0] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1.0+1.0*$nb2)] [expr $AbutInfo($name-nodeNum)+0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+1.0*$nb2+1)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+$nb2+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(1+8.0*$nb+5.0*$nb2)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn+1)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			# springs connecting the abutment array to fixity
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			global deckSpringArrayEles
			set deckSpringArrayEles {}
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+0] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2)]				
			for {set nn 1} {$nn <= [expr int($nb2-1)]} {incr nn} { 
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb)]  -mat   [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"  
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int($nn+8.0*$nb+1.0*$nb2)]  -mat   [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]
			}		

			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"  
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23]  \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir" 

			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]

			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+38]  \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"  
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+38]  \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir" 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]

			# define regions for possible increased abutment damping, should include all elements
			region [expr $AbutInfo($name-shift)+0] -ele $deckSpringArrayEles
			# define regions for bearing pad and longitudinal recorders
			region [expr $AbutInfo($name-shift)+2] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb+1.0)] \n				[expr $AbutInfo($name-eleNum)+int(9.0*$nb+1.0)] [expr $AbutInfo($name-eleNum)+int(10.0*$nb)] \n				[expr $AbutInfo($name-eleNum)+int(10.0*$nb+1.0)]
			# define regions for transverse shear key recorders
			region [expr $AbutInfo($name-shift)+3] -ele [expr $AbutInfo($name-eleNum)+int(8.0*$nb)]

		} elseif { $temp2 > 0 } {
				# For an odd number of boxes
			set nb2 [expr int(($totalb2+3.0)/2.0)]
			for {set nn 1} {$nn <= [expr int($nb2)]} {incr nn} {
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+$nb2)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr -$x($nn)]
				set zz [expr  $z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				set xx [expr  $x($nn)]
				set zz [expr -$z($nn)]
				set xx1 [expr  $xx * $cosabut + $zz*$sinabut]
				set zz1 [expr -$xx * $sinabut + $zz*$cosabut]
				node [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  [expr $xx1+$xi]  [expr $zz1+$zi]  $yi
				if { [llength $AbutInfo($name-abutNode)] == 2 } {
					if {$nn<int($nb2)} {
						#fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  1 1 1 1 1 1
						#fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  1 1 1 1 1 1
							#puts "fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)]  1 1 1 1 1 1"
							#puts "fix [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)]  1 1 1 1 1 1"
					} elseif {$nn==int($nb2)} {		
						equalDOF [expr $AbutInfo($name-nodeNum)+int(5.0*$nb-1)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)]  1 2 3 4 5 6
						equalDOF [expr $AbutInfo($name-nodeNum)+int(6.0*$nb)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)]  1 2 3 4 5 6					
						if { [llength $AbutInfo($name-abutNode)] == 2 } {
							equalDOF [lindex $AbutInfo($name-abutNode) 0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)]  1 2 3 4 5 6
							equalDOF [lindex $AbutInfo($name-abutNode) 1] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  1 2 3 4 5 6
						} else {
							equalDOF $AbutInfo($name-abutNode) 0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)]  1 2 3 4 5 6
							equalDOF $AbutInfo($name-abutNode) [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  1 2 3 4 5 6
						}		
							if { [llength $AbutInfo($name-abutNode)] == 2 } {
							} else {
							}		
					}		
				} else {
					error "SDC2010SandAbutment requires either 1 or 2 abutNodes as input"
				}
			} 

			# deck array 
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+1)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+1.0)] [expr $AbutInfo($name-nodeNum)+0]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nb2+1.0)]  [expr $AbutInfo($name-nodeNum)+0] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+1.0)]  \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} {
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nb2+$nn+1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn+1.0)]  \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}	
			element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12.0*$nb+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+1)] \
				10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} { 
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+9.0*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
				element elasticBeamColumn [expr $AbutInfo($name-eleNum)+int(12*$nb+$nn+10.*$nb2)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn+1.0)] \
					10.0 5.0e10 1.5e7 1.0e3 1.0e3 1.0e3 $AbutInfo($name-dTransf)
			}
			# springs connecting the deck array to the abutment array
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			global deckSpringArrayEles
			set deckSpringArrayEles {}	
			for {set nn 1} {$nn <= [expr int($nb2-1.0)]} {incr nn} {
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+4.0*$nb2+$nn-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nn)]  -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
				eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2+$nn)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2+$nn)]  -mat [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
					-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir2"
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+4.0*$nb2+$nn)]
				lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2+$nn)]
			}
			
			# springs connecting the abutment array to fixity
			# note: local z for this element is opposite to global Z when orient = -1 (transverse material must be symmetric then)
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+41] [expr $AbutInfo($name-matNum)+23] \
				-dir  1 3 -doRayleigh $doRayleigh -orient  $distributedSpringDir2"
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+5.0*$nb2)] 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+6.0*$nb2)]  

			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+5.0*$nb2-1.0)] [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+$nb2)] -mat  [expr $AbutInfo($name-matNum)+38] \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
			eval "element zeroLength  [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+6.0*$nb2)]  [expr $AbutInfo($name-nodeNum)+int(8.0*$nb+2.0*$nb2)] -mat  [expr $AbutInfo($name-matNum)+38] \
				-dir  2 -doRayleigh $doRayleigh -orient  $abutDir"
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+7.0*$nb2)] 
			lappend deckSpringArrayEles [expr $AbutInfo($name-eleNum)+int(12*$nb+8.0*$nb2)]  

			# define regions for possible increased abutment damping, should include all elements
			region [expr $AbutInfo($name-shift)+0] -ele $deckSpringArrayEles
			
		}
	}
	
		close  $fabut
file delete $abutmentModelNodeCoor
	global abutRecRegion
	set abutRecRegion {}
	lappend abutRecRegion [expr $AbutInfo($name-shift)+0]

}

proc ::SDC2010SandAbutment::Op_information {name} {
	# information return
	
	variable AbutInfo

    return [list $AbutInfo($name-threeD)]
}

proc ::SDC2010SandAbutment::Op_recorder {name fstub} {
	# recorder definition
	
    variable AbutInfo
   
    # node recorders
    recorder Node -file [format "output/%snd_abut_%i.out" $fstub $AbutInfo($name-tag)] -region [expr $AbutInfo($name-shift)+1] -dof 1 2 3 disp
	
    # element recorders
	recorder Element -file [format "output/%sel_abut_%i.out" $fstub $AbutInfo($name-tag)] -region [expr $AbutInfo($name-shift)+0] deformationANDforces
	
	# material recorders
	set filef [open abutMats_$AbutInfo($name-tag).out "r"]
    set ident 0
    while {-1 != [gets $filef line] } {
        if { [lindex $line 0] != "%" } {
            set cmds [split $line]
            incr ident
			set recobj "recorder Element -file [format "output/%sem_abut_%i_%i.out" $fstub $AbutInfo($name-tag) $ident] -region $line stressStrain"
			eval $recobj
        }
    }
    close $filef
}

proc ::SDC2010SandAbutment::Op_post_static {name static_args} {
	# post-process static analysis data
	
    variable AbutInfo
    
	# Now parse data from static_args
	scan $static_args "%s %s %i %s" fstub filehandle push_type texttag
    
    # now look in each material abutment file and extract data
	# NOTE: this depends on how the recorders were specified in abutment files
	# file *_1 is the neoprene bearing longitudinal
	# file *_2 is the neoprene bearing transverse
	set fL1 [format "output/%sem_abut_%i_1.out" $fstub $AbutInfo($name-tag)]
	set fL2 [format "output/%sem_abut_%i_2.out" $fstub $AbutInfo($name-tag)]
	
	set dout [FirstLast $fL1 9 "1 2 3 4"]
	scan $dout "%f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f" fdLiL1 fdLmaxL1 fdLminL1 fdLrL1 udLiL1 udLmaxL1 udLminL1 udLrL1 \n													             fdLiL2 fdLmaxL2 fdLminL2 fdLrL2 udLiL2 udLmaxL2 udLminL2 udLrL2
	set dout [FirstLast $fL2 9 "1 2 3 4"]
	scan $dout "%f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f" fdLiT1 fdLmaxT1 fdLminT1 fdLrT1 udLiT1 udLmaxT1 udLminT1 udLrT1 \n													             fdLiT2 fdLmaxT2 fdLminT2 fdLrT2 udLiT2 udLmaxT2 udLminT2 udLrT2
	
	set udLmaxL [max [expr abs($udLmaxL1)] [expr abs($udLmaxL2)]]
	set udLmaxT [max [expr abs($udLmaxT1)] [expr abs($udLmaxT2)]]
	set udLminL [max [expr abs($udLminL1)] [expr abs($udLminL2)]]
	set udLminT [max [expr abs($udLminT1)] [expr abs($udLminT2)]]
	set udLmL [max $udLmaxL $udLminL]
	set udLmT [max $udLmaxT $udLminT]
	
	# file *_3 is the shear key transverse
	set fLsk [format "output/%sem_abut_%i_3.out" $fstub $AbutInfo($name-tag)]
	
	set dout [FirstLast $fLsk 9 "1 2"]
	scan $dout "%f %f %f %f %f %f %f %f" fLski fLskmax fLskmin fLskr uLski uLskmax uLskmin uLskr
	set datmL [XatMaxY $fLsk 1 2]
	
	# file *_4 is the gap longitudinal response, a bit more complicated because we want 
	# relative movement of the backwall only on the compression side
	# NOTE, all quantities are negative in compression regardless if looking at L or R side
	set fLgL [format "output/%sem_abut_%i_4.out" $fstub $AbutInfo($name-tag)]
	set gLfile [open $fLgL "r"]
	set max_dispL 0.0; set max_loadL 0.0; set prev_forcL 0.0
	set gapL 0.0
	
	while { -1 != [gets $gLfile lineL] } {
	   if { [string length $lineL] > 4 } {
		  set cmdL [specialSplit $lineL]
		  set kl [llength $cmdL]
	
		  if { [string is double [lindex $cmdL 0]] } {
			 set temp_loadL [min [lindex $cmdL 0] [lindex $cmdL 2]]
			 set temp_dispL [min [lindex $cmdL 1] [lindex $cmdL 3]]
	
			 if { $temp_loadL < $max_loadL } {
				set max_loadL $temp_loadL
			 }
			 if { $temp_dispL < $max_dispL } {
				set max_dispL $temp_dispL
			 }
			 if { $temp_loadL < -1.0e-5 & $prev_forcL > -1.0e-5 } {
				set gapL $temp_dispL
			 }
			 
			 set prev_forcL $temp_loadL
		  }
	   }
	}
	if { $gapL < -1.0e-5 } {
		set bwallL [expr $max_dispL-$gapL]
	} else {
		set bwallL -1.0e-5
	}
	close $gLfile
	
	# file *_5 are the vertical materials (bearing pad and embankment)
	# might just want to look at the max left and right end vertical displacements for now


	puts $filehandle "Max_displ. abut $AbutInfo($name-tag) bearing long.     [expr abs($udLmL)]"
	puts $filehandle "Max_displ. abut $AbutInfo($name-tag) bearing tran.     [expr abs($udLmT)]"
	puts $filehandle "Max_abs_displ. abut $AbutInfo($name-tag) bearing       [max [expr abs($udLmL)] [expr abs($udLmT)]]"
	puts $filehandle "Max_force abut $AbutInfo($name-tag) shear key          [max [expr abs($fLskmax)] [expr abs($fLskmin)]]"
	puts $filehandle "Max_force abut $AbutInfo($name-tag) backwall           [expr $max_loadL]"
	puts $filehandle "Max_displ. of abut $AbutInfo($name-tag) backwall       $bwallL"
}

proc ::SDC2010SandAbutment::Op_post_dynamic {name dynamic_args} {
    # post-process dynamic analysis data
    
    variable AbutInfo

}

