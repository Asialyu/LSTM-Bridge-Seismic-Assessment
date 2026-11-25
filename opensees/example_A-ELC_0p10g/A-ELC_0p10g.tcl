# A-ELC_0p10g.tcl --
#
#        The main .tcl file for OpenSees.
#
#            MSBridge (Beta 1.0.1.20324)
#        OpenSees Analysis of Multi-Span Bridges
#      Copyright (c) 2019 All Rights Reserved.
#

wipe

logFile A-ELC_0p10g.log

puts "Analysis started at: [clock format [clock seconds]]\n"
# clock format [clock seconds] -format "%T"
set startT [clock seconds]

set parallel 0; # 0 -- sequential run (e.g., on a PC)
                # 1 -- parallel run
set optionFile "../../../options.tcl"
if {[file exists $optionFile]==1} {
  source $optionFile; # this file will set parallel to 0 or 1
}
set OutputDir "."
switch $parallel {
  0 {
    set solver "ProfileSPD"
#    set solver "SparseSPD"
#    set solver "SparseSPD 4"
#    set solver "BandGeneral"
  }
  1 {
    set solver "Mumps -ICNTL14 50"
  }
}

set outfmt "-file"
set numberer "RCM"

# Unit system in this file: US
# define UNITS ---------------------------------------------
set inTom   2.540000e-002
set in 1.; 		# define basic units -- output units
set kip 1.;		# define basic units -- output units
set sec 1.;		# define basic units -- output units
set ft [expr 12.*$in]; 		# define engineering units
set ft2 [expr $ft*$ft]; 		
set ft4 [expr $ft2*$ft2]; 		
set ksi [expr $kip/pow($in,2)];
set psi [expr $ksi/1000.];
set lbf [expr $psi*$in*$in];			# pounds force
set pcf [expr $lbf/pow($ft,3)];		# pounds per cubic foot
set psf [expr $lbf/pow($ft,2)];		# pounds per square foot
set in2 [expr $in*$in]; 				# inch^2
set in4 [expr $in*$in*$in*$in]; 		# inch^4
set g 9.81; 	# gravitational acceleration

set psfTokPa 4.78802600e-002
set ksfTokPa 4.78802600e+001
set psiTokPa 6.89475720e+000
set ksiTokPa 6.89475720e+003
set ftTom 3.04800000e-001
set kipTokN 4.44822170e+000
set kipftTokNm 1.35581790e+000
set kip_ftTokN_m 1.45939040e+001
set lb_ftTokN_m 1.45939040e-002
set pcfToton_m3 1.60184600e-002
set pcfTokN_m3 1.57141090e-001
set kip_ftToton_m 1.48765586e+000
set lbmToMg 4.53592370e-004
set gamma 0.6
set am   2.154200e-001
set ak   9.094600e-004
set numSteps 2000
set compdT 0.020000
set dT 0.01
# remove files so post-processing won't be able to read wrong files
file delete $OutputDir/A-ELC_0p10g.tim
file delete $OutputDir/A-ELC_0p10g.dsp
file delete $OutputDir/A-ELC_0p10g.frq
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.a*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.c*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.de*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.ds*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.f*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.i*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.la*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.p*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.ra*]"
eval "file delete {*}[glob -nocomplain A-ELC_0p10g.s*]"
file delete $OutputDir/traceStop.txt

# SDC 1.6 (Nov. 2010)
# use 1.0 if not ESA method
# Adjust abutment stiffness based on the abutment displacement coefficient R
# R = delta_D / delta_eff
# If R <= 2: delta_D is the displacement demand
# If R >= 4: scale the effective abutment stiffness K_eff by 0.1 and recalculate delta_D
# If 2 < R < 4, do interpolation for the scale factor (between 0.1 and 1) and recalculate delta_D
set abutKfactor 1
model basic -ndm 3 -ndf 6
node      1 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node      2 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node      3 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node      4 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node      5 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node      6 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node      7 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node      8 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node      9 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node     10 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node     11 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node     12 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node     13 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     14 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     15 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node     16 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node     17 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node     18 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node     19 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node     20 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     21 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     22 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node     23 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node     24 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node     25 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node     26 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node     27 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     28 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     29 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node     30 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node     31 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node     32 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node     33 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node     34 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     35 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     36 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -2.200000e+001*$ft*$inTom] 
node     37 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.760000e+001*$ft*$inTom] 
node     38 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -1.320000e+001*$ft*$inTom] 
node     39 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -8.800000e+000*$ft*$inTom] 
node     40 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr  -4.400000e+000*$ft*$inTom] 
node     41 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     42 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     43 [expr   6.000000e+001*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     44 [expr   6.000000e+001*$ft*$inTom] [expr  -4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     45 [expr   6.000000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     46 [expr   6.000000e+001*$ft*$inTom] [expr   4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     47 [expr   6.000000e+001*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     48 [expr   1.200000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     49 [expr   1.200000e+002*$ft*$inTom] [expr  -4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     50 [expr   1.200000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     51 [expr   1.200000e+002*$ft*$inTom] [expr   4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     52 [expr   1.200000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     53 [expr   1.800000e+002*$ft*$inTom] [expr  -9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     54 [expr   1.800000e+002*$ft*$inTom] [expr  -4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     55 [expr   1.800000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     56 [expr   1.800000e+002*$ft*$inTom] [expr   4.500000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     57 [expr   1.800000e+002*$ft*$inTom] [expr   9.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     58 [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     59 [expr   1.200000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     60 [expr   2.400000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     61 [expr   3.600000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     62 [expr   4.800000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     63 [expr   6.000000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     64 [expr   7.200000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     65 [expr   8.400000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     66 [expr   9.600000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     67 [expr   1.080000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     68 [expr   1.200000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     69 [expr   1.320000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     70 [expr   1.440000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     71 [expr   1.560000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     72 [expr   1.680000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     73 [expr   1.800000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     74 [expr   1.920000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     75 [expr   2.040000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     76 [expr   2.160000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     77 [expr   2.280000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     78 [expr   2.400000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     79 [expr   0.000000e+000*$ft*$inTom] [expr  -1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     80 [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     81 [expr   0.000000e+000*$ft*$inTom] [expr   1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     82 [expr   2.400000e+002*$ft*$inTom] [expr  -1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     83 [expr   2.400000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     84 [expr   2.400000e+002*$ft*$inTom] [expr   1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     85 [expr   0.000000e+000*$ft*$inTom] [expr  -1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     86 [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     87 [expr   0.000000e+000*$ft*$inTom] [expr   1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     88 [expr   2.400000e+002*$ft*$inTom] [expr  -1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     89 [expr   2.400000e+002*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 
node     90 [expr   2.400000e+002*$ft*$inTom] [expr   1.950000e+001*$ft*$inTom] [expr   0.000000e+000*$ft*$inTom] 

# column base condition
fix 1   1 1 1  1 1 1
fix 8   1 1 1  1 1 1
fix 15   1 1 1  1 1 1
fix 22   1 1 1  1 1 1
fix 29   1 1 1  1 1 1
fix 36   1 1 1  1 1 1

# fix left abutment
fix     85 1 1 1  1 1 1
fix     86 1 1 1  1 1 1
fix     87 1 1 1  1 1 1

# fix right abutment
fix     88 1 1 1  1 1 1
fix     89 1 1 1  1 1 1
fix     90 1 1 1  1 1 1

equalDOF      7     43  1 2 3 4 5 6
equalDOF     14     47  1 2 3 4 5 6
equalDOF     21     48  1 2 3 4 5 6
equalDOF     28     52  1 2 3 4 5 6
equalDOF     35     53  1 2 3 4 5 6
equalDOF     42     57  1 2 3 4 5 6
equalDOF     45     63  1 2 3 4 5 6
equalDOF     50     68  1 2 3 4 5 6
equalDOF     55     73  1 2 3 4 5 6


# connect left deck-end nodes
equalDOF     58     80  1 2 3 4 5 6

# connect right deck-end nodes
equalDOF     78     83  1 2 3 4 5 6

set numSteps3rdRun 20
set timeStep3rdRun 1

geomTransf LinearWithPDelta 1101   0.000000e+000   1.000000e+000 0
geomTransf LinearWithPDelta 1102   0.000000e+000   1.000000e+000 0
geomTransf LinearWithPDelta 1103   0.000000e+000   1.000000e+000 0
geomTransf LinearWithPDelta 1001 0 1 0
geomTransf LinearWithPDelta 1002 0 0 1
geomTransf LinearWithPDelta 1301   0.000000e+000   1.000000e+000 0; # Bent 2
geomTransf LinearWithPDelta 1302   0.000000e+000   1.000000e+000 0; # Bent 3
geomTransf LinearWithPDelta 1303   0.000000e+000   1.000000e+000 0; # Bent 4
geomTransf LinearWithPDelta 1003 0 1 0

set numIntgrPtsCol 5


# #################### Column Section: Cross Section 1 ####################


set coreTag 2001
set coverTag 2002
set steelTag 2003

uniaxialMaterial Concrete02 $coreTag [expr -6.740958e+003*$psiTokPa] -3.700000e-003 [expr -6.530629e+003*$psiTokPa] -3.609000e-002 1.000000e-001 [expr 9.437341e+002*$psiTokPa] [expr 2.550903e+005*$psiTokPa]
uniaxialMaterial Concrete02 $coverTag [expr -4.000000e+003*$psiTokPa] -2.000000e-003 [expr 0.000000e+000*$psiTokPa] -6.000000e-003 1.000000e-001 [expr 5.600000e+002*$psiTokPa] [expr 2.800000e+005*$psiTokPa]
uniaxialMaterial Steel02 $steelTag [expr 6.671750e+004*$psiTokPa] [expr 2.900000e+007*$psiTokPa] 1.000000e-002 1.500000e+001 9.250000e-001 1.500000e-001
set strainLimit 0.120000
set wrappedTag 2003
set steelTag2 2009
uniaxialMaterial MinMax     $steelTag2  $wrappedTag  -min -$strainLimit -max $strainLimit
set pSection 2005
# circular column
section Fiber $pSection {
    patch circ $coreTag 10 2 0. 0. [expr 0.000000e+000*$inTom] [expr 1.103125e+001*$inTom] 0.000000e+000 3.600000e+002
    patch circ $coreTag 20 5 0. 0. [expr 1.103125e+001*$inTom] [expr 2.206250e+001*$inTom] 0.000000e+000 3.600000e+002
    patch circ $coverTag 20 1 0. 0. [expr 2.206250e+001*$inTom] [expr 2.400000e+001*$inTom] 0.000000e+000 3.600000e+002
    layer circ $steelTag2 30 [expr 1.266769e+000*$inTom*$inTom] 0. 0. [expr 2.142750e+001*$inTom] 1.200000e+001 3.600000e+002
}
set Sec1Tag3D 2000;                 # ID tag for combined behavior for 3D model
set Sec1Tag3Dcore 2007;                 # ID tag for combined behavior for 3D model
uniaxialMaterial Elastic 2006 1e10;  # define elastic torsional stiffness
section Aggregator $Sec1Tag3D 2006 T -section $pSection; # combine section properties

#Tracking for first rebar yield
set initYield {}
lappend initYield 2009 0.002301 

set SecTag3D $Sec1Tag3D
element forceBeamColumn       1      1      2 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       2      2      3 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       3      3      4 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       4      4      5 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       5      5      6 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       6      8      9 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       7      9     10 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       8     10     11 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn       9     11     12 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      10     12     13 1301 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      11     15     16 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      12     16     17 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      13     17     18 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      14     18     19 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      15     19     20 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      16     22     23 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      17     23     24 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      18     24     25 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      19     25     26 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      20     26     27 1302 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      21     29     30 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      22     30     31 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      23     31     32 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      24     32     33 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      25     33     34 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      26     36     37 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      27     37     38 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      28     38     39 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      29     39     40 1303 Lobatto $SecTag3D $numIntgrPtsCol
set SecTag3D $Sec1Tag3D
element forceBeamColumn      30     40     41 1303 Lobatto $SecTag3D $numIntgrPtsCol

set Iy  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set Iz  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set A  [expr 1.256637e+001*$ft2*$inTom*$inTom]
set E  [expr 1.000000e-010*$ksi*$ksiTokPa]
set G  [expr 1.000000e-010*$ksi*$ksiTokPa]
set Jx [expr 2.513274e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
element elasticBeamColumn     31      1      2   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     32      2      3   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     33      3      4   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     34      4      5   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     35      5      6   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     36      8      9   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     37      9     10   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     38     10     11   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     39     11     12   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     40     12     13   $A $E $G $Jx $Iy $Iz 1101 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     41     15     16   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     42     16     17   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     43     17     18   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     44     18     19   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     45     19     20   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     46     22     23   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     47     23     24   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     48     24     25   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     49     25     26   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     50     26     27   $A $E $G $Jx $Iy $Iz 1102 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     51     29     30   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     52     30     31   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     53     31     32   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     54     32     33   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     55     33     34   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     56     36     37   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     57     37     38   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     58     38     39   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     59     39     40   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     60     40     41   $A $E $G $Jx $Iy $Iz 1103 -mass [expr 1.884956e+003/1000.*$kip_ftToton_m]

pattern Plain 201 Linear {
    eleLoad -ele 31 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 32 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 33 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 34 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 35 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 36 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 37 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 38 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 39 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 40 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 41 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 42 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 43 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 44 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 45 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 46 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 47 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 48 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 49 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 50 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 51 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 52 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 53 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 54 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 55 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 56 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 57 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 58 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 59 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
    eleLoad -ele 60 -type -beamUniform 0.0 0.0 [expr -1.884956e+003/1000.*$kip_ftTokN_m/$numSteps3rdRun/$timeStep3rdRun*2]
}

# Column top rigid links

equalDOF 6 7  1 2 3 4 5 6

equalDOF 13 14  1 2 3 4 5 6

equalDOF 20 21  1 2 3 4 5 6

equalDOF 27 28  1 2 3 4 5 6

equalDOF 34 35  1 2 3 4 5 6

equalDOF 41 42  1 2 3 4 5 6

# Bent cap
set pSection 3000

# Bentcap Section: Bentcap 1
# E*Iy
uniaxialMaterial Elastic   3501 [expr 4.061000e+003*3.200000e+001*144*$kipTokN*$ftTom*$ftTom]
# E*Iz
uniaxialMaterial Elastic   3502 [expr 4.061000e+003*7.200000e+001*144*$kipTokN*$ftTom*$ftTom]
# G*A
uniaxialMaterial Elastic   3503 [expr 1.667940e+003*2.400000e+001*144*$kipTokN]
# G*A
uniaxialMaterial Elastic   3504 [expr 1.667940e+003*2.400000e+001*144*$kipTokN]
# G*Jx
uniaxialMaterial Elastic   3505 [expr 1.667940e+003*7.512500e+001*144*$kipTokN*$ftTom*$ftTom]
# E*A
uniaxialMaterial Elastic   3506 [expr 4.061000e+003*2.400000e+001*144*$kipTokN]
eval "section Aggregator [expr $pSection+1] 3506 P 3501 My 3502 Mz 3505 T 3503 Vy 3504 Vz"
set numIntgrPts 3
eval "element forceBeamColumn      61     43     44 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      62     44     45 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      63     45     46 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      64     46     47 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      65     48     49 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      66     49     50 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      67     50     51 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      68     51     52 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      69     53     54 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      70     54     55 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      71     55     56 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      72     56     57 1002 Lobatto [expr $pSection+1] $numIntgrPts"
set Iy  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set Iz  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set A  [expr 1.256637e+001*$ft2*$inTom*$inTom]
set E  [expr 1.000000e-010*$ksi*$ksiTokPa]
set G  [expr 1.000000e-010*$ksi*$ksiTokPa]
set Jx [expr 2.513274e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
element elasticBeamColumn     73     43     44   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     74     44     45   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     75     45     46   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     76     46     47   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     77     48     49   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     78     49     50   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     79     50     51   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     80     51     52   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     81     53     54   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     82     54     55   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     83     55     56   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]
element elasticBeamColumn     84     56     57   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 3.600000e+003/1000.*$kip_ftToton_m]

# Deck
set pSection 4000

# Deck Section: Deck 1
# E*Iy
uniaxialMaterial Elastic   4501 [expr 4.061000e+003*3.560430e+002*144*$kipTokN*$ftTom*$ftTom]
# E*Iz
uniaxialMaterial Elastic   4502 [expr 4.061000e+003*8.235630e+003*144*$kipTokN*$ftTom*$ftTom]
# G*A
uniaxialMaterial Elastic   4503 [expr 1.667940e+003*6.811100e+001*144*$kipTokN]
# G*A
uniaxialMaterial Elastic   4504 [expr 1.667940e+003*6.811100e+001*144*$kipTokN]
# G*Jx
uniaxialMaterial Elastic   4505 [expr 1.667940e+003*9.783810e+002*144*$kipTokN*$ftTom*$ftTom]
# E*A
uniaxialMaterial Elastic   4506 [expr 4.061000e+003*6.811100e+001*144*$kipTokN]
eval "section Aggregator [expr $pSection+1] 4506 P 4501 My 4502 Mz 4505 T 4503 Vy 4504 Vz"
set numIntgrPts 3
eval "element forceBeamColumn      85     58     59 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      86     59     60 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      87     60     61 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      88     61     62 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      89     62     63 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      90     63     64 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      91     64     65 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      92     65     66 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      93     66     67 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      94     67     68 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      95     68     69 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      96     69     70 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      97     70     71 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      98     71     72 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn      99     72     73 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn     100     73     74 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn     101     74     75 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn     102     75     76 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn     103     76     77 1002 Lobatto [expr $pSection+1] $numIntgrPts"
eval "element forceBeamColumn     104     77     78 1002 Lobatto [expr $pSection+1] $numIntgrPts"
set Iy  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set Iz  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set A  [expr 1.256637e+001*$ft2*$inTom*$inTom]
set E  [expr 1.000000e-010*$ksi*$ksiTokPa]
set G  [expr 1.000000e-010*$ksi*$ksiTokPa]
set Jx [expr 2.513274e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
element elasticBeamColumn    105     58     59   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    106     59     60   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    107     60     61   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    108     61     62   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    109     62     63   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    110     63     64   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    111     64     65   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    112     65     66   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    113     66     67   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    114     67     68   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    115     68     69   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    116     69     70   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    117     70     71   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    118     71     72   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    119     72     73   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    120     73     74   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    121     74     75   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    122     75     76   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    123     76     77   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]
element elasticBeamColumn    124     77     78   $A $E $G $Jx $Iy $Iz 1002 -mass [expr 1.021600e+004/1000.*$kip_ftToton_m]

# Abutment rigid links
set Iy  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set Iz  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set A  [expr 1.256637e+001*$ft2*$inTom*$inTom]
set E  [expr 4.350000e+009*$ksi*$ksiTokPa]
set G  [expr 1.677000e+009*$ksi*$ksiTokPa]
set Jx [expr 2.513274e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
element elasticBeamColumn    125     79     80   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    126     80     81   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    127     82     83   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    128     83     84   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    129     85     86   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    130     86     87   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    131     88     89   $A $E $G $Jx $Iy $Iz 1002
element elasticBeamColumn    132     89     90   $A $E $G $Jx $Iy $Iz 1002

# add dummy weak element to connect abutment and deck (to avoid disconnected graph for sparse solvers)
set Iy  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set Iz  [expr 1.256637e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
set A  [expr 1.256637e+001*$ft2*$inTom*$inTom]
set E  [expr 1.000000e-010*$ksi*$ksiTokPa]
set G  [expr 1.000000e-010*$ksi*$ksiTokPa]
set Jx [expr 2.513274e+001*$ft2*$ft2*$inTom*$inTom*$inTom*$inTom]
uniaxialMaterial Elastic 30001  [expr 1e-10*$kipTokN/$inTom]
element zeroLength 133 86 58 -mat  30001 -dir 1
element zeroLength 134 89 78 -mat  30001 -dir 1

#create trace file for progress bar display
set tracefnameTot "$OutputDir/traceTot.txt"
set tracefnameCurr "$OutputDir/traceCurr.txt"

set columnNodes {}
for {set i 1 } {$i <= 42 } {incr i 1} { lappend columnNodes [expr $i] }
set columnBaseNodes {}
lappend columnBaseNodes 1 8 15 22 29 36 
set piercapNodes {}
for {set i 43 } {$i <= 57 } {incr i 1} { lappend piercapNodes [expr $i] }
set deckNodes {}
for {set i 58 } {$i <= 78 } {incr i 1} { lappend deckNodes [expr $i] }
set deckendNodes {}
for {set i 79 } {$i <= 84 } {incr i 1} { lappend deckendNodes [expr $i] }
set abutNodes {}
for {set i 85 } {$i <= 90 } {incr i 1} { lappend abutNodes [expr $i] }
set soilSpringNodes {}
set soilSpringPileNodes {}
set columnEles {}
for {set i 1 } {$i <= 30 } {incr i 1} { lappend columnEles [expr $i] }
set piercapEles {}
for {set i 61 } {$i <= 72 } {incr i 1} { lappend piercapEles [expr $i] }
set deckEles {}
for {set i 85 } {$i <= 104 } {incr i 1} { lappend deckEles [expr $i] }
set pileShaftEles {}
set leftAbutPileEles {}
set rightAbutPileEles {}
set soilSpringEles {}
set leftAbutSoilSpringEles {}
set rightAbutSoilSpringEles {}
set deckHingeEles {}
set isolationBearingEles {}
set deckendEles {}
for {set i 125 } {$i <= 128 } {incr i 1} { lappend deckendEles [expr $i] }
set foundationMatrixEles {}
set stemwallEles {}

# create control nodes for abutment model
# Deckend fixity if any

set deckNodeL  58
set deckNodeR  78
# center node of left abutment
set abutNodeL  86
# center node of right abutment
set abutNodeR  89
# two edge nodes of left abutment (sequence: +y node and then -y node)
set abutNodeListL  [list 87 85]
# two edge nodes of right abutment (sequence: +y node and then -y node)
set abutNodeListR  [list 90 88]
# center node of left abutment
set abutFoundNodeL  $abutNodeL
# center node of right abutment
set abutFoundNodeR  $abutNodeR

remove recorders
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.dg -time -node $columnNodes $piercapNodes $deckNodes $deckendNodes $abutNodes $soilSpringNodes -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.abutdg -time -node $deckNodeL $abutNodeL $abutFoundNodeL $deckNodeR $abutNodeR $abutFoundNodeR -dof 1 2 3 disp"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.ifpg -time -ele $columnEles inflectionPoint"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.dftg -time -ele $columnEles tangentDrift"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.colforceg -time -ele $columnEles localForces"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.coldispg -time -node $columnNodes -dof 1 2 3 4 5 6 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.colaccg -time -node $columnNodes -dof 1 2 3 accel"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.colbasedispg -time -node $columnBaseNodes -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.deckdispg -time -node $deckNodes -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.deckaccg -time -node $deckNodes -dof 1 2 3 accel"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.deckforceg -time -ele $deckEles localForces"

numberer $numberer
eval "system $solver"
test NormDispIncr 1.0e-6 300 2
algorithm ModifiedNewton
constraints Penalty 1.e18 1.e18
#integrator Newmark 1.5  1.
#analysis Transient 
integrator LoadControl 1 1 1 1
analysis Static 

set fileId [open $tracefnameTot "w"]
puts $fileId "1 [expr $numSteps3rdRun]"
close $fileId

set fileId [open $tracefnameCurr "w"]
puts $fileId 0
close $fileId

puts "Application of own weight (Stage 1: own weight without abutment model activated):"

set ok [analyze [expr $numSteps3rdRun/2]]

if {$ok != 0} { return $ok }

loadConst -time 0.
pattern Plain 202 Linear {
    eleLoad -ele 61 62 63 64 65 66 67 68 69 70 71 72 -type -beamUniform 0.0 [expr -3.600000e+000*$kip_ftTokN_m/($numSteps3rdRun-$numSteps3rdRun/2)/$timeStep3rdRun]
}

pattern Plain 203 Linear {
    eleLoad -ele 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 -type -beamUniform 0.0 [expr -1.021600e+001*$kip_ftTokN_m/($numSteps3rdRun-$numSteps3rdRun/2)/$timeStep3rdRun]
}

source Abutment.tcl
geomTransf Linear  102  0 1 1
set bentTransf 102
set Lspan [expr 60*$ft*$inTom]
# default parameter values (should not need to change these)
set elastic 0
set threeD 1
set MAT_SHIFT 10000

# parameters coming from MSBridge interface
set fy [expr 66717.5*$psiTokPa]
set fcFndn [expr 4000*$psiTokPa]
set gammaConcrete [expr 145*$pcfTokN_m3]
set gammaSteel [expr 490*$pcfTokN_m3]
set gap [expr 1*$inTom]
set deckUnitWeight [expr 10.216*$kip_ftTokN_m]
set dw [expr 39*$ft*$inTom]
set dd [expr 6*$ft*$inTom]
set Hcol [expr 22*$ft*$inTom]
set NSpr 2

# set Tcl lists containing generic input values
set argListA [list $elastic $threeD $bentTransf $fy $fcFndn $gammaConcrete $gammaSteel]

# for SDC2010SandAbutment
set SDC2010SandMass [expr 0*$lbmToMg]
set SDC2010SandVs [expr 492.13*$ft*$inTom]
set SDC2010SandRho [expr 109.87*$pcfToton_m3]
set SDC2010SandSlope [expr 0.5]
set SDC2010SandSkewAngleL [expr 0]
set SDC2010SandSkewAngleR [expr 0]
set SDC2010SandKi [expr 50*$kipTokN/$in/$ft/$inTom/$inTom]
set SDC2010SandPu [expr 5*$kipTokN/$ft/$ft/$inTom/$inTom]
set argListAbutSDC2010SandL [list SDC2010SandAbutment $SDC2010SandMass $SDC2010SandVs $SDC2010SandRho $SDC2010SandSlope $SDC2010SandSkewAngleL $SDC2010SandKi $SDC2010SandPu $abutKfactor]
set argListAbutSDC2010SandR [list SDC2010SandAbutment $SDC2010SandMass $SDC2010SandVs $SDC2010SandRho $SDC2010SandSlope $SDC2010SandSkewAngleR $SDC2010SandKi $SDC2010SandPu $abutKfactor]


# Define abutments -----------------------------------------------------------------------------------------------------------
#   limits: 10 different abutment types
# 	abutments use tagged objects: 6001-8000
# 	(includes elements, nodes, materials, sections, and geometric transformations)
# 	NOTE: all numbers above are shifted according to MAT_SHIFT
# Abutments are slightly different to the other modules in that the initialization phase is
# required for each abutment realization, so separate types are "created" even if abutType is the same
set argListAbutL $argListAbutSDC2010SandL
set argListAbutR $argListAbutSDC2010SandR

# derived quantities
set abut_loadL [expr $deckUnitWeight*$Lspan/2.0]
set abut_loadR [expr $deckUnitWeight*$Lspan/2.0]
		
# left abutment
Abutment "create" 1 [concat $MAT_SHIFT $argListAbutL $argListA $deckNodeL [list $abutNodeListL]  -1 $gap $abut_loadL $dw $dd $Hcol $NSpr]

set deckArrayEleListL $deckSpringArrayEles

# right abutment
Abutment "create" 2 [concat $MAT_SHIFT $argListAbutR $argListA $deckNodeR [list $abutNodeListR]   1  $gap $abut_loadR $dw $dd $Hcol $NSpr]

set deckArrayEleListR $deckSpringArrayEles


set fileId [open $tracefnameTot "w"]
puts $fileId "11 [expr $numSteps3rdRun]"
close $fileId

set fileId [open $tracefnameCurr "w"]
puts $fileId 0
close $fileId

puts "
Application of own weight (Stage 2: SDC 2010 Sand abutment model applied):"
set ok [analyze [expr $numSteps3rdRun-$numSteps3rdRun/2]]
if {$ok != 0} { return $ok }
puts "First run done.
"

#############################
# Loading (Pushover, or base shaking) 
#############################

# rezero time
wipeAnalysis
loadConst -time 0.0

# base input motion 
pattern UniformExcitation  1  1  -accel "Series -fileTime $OutputDir/acc_time.txt -filePath $OutputDir/acc_value.txt -factor [expr    1.00000e+000*$g]"
pattern UniformExcitation  2  2  -accel "Series -fileTime $OutputDir/acc_timeY.txt -filePath $OutputDir/acc_valueY.txt -factor [expr    8.50000e-001*$g]"
pattern UniformExcitation  3  3  -accel "Series -fileTime $OutputDir/acc_timeZ.txt -filePath $OutputDir/acc_valueZ.txt -factor [expr    6.50000e-001*$g]"

# output responses
remove recorders
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.abutdsp -time  -node $deckNodeL $abutNodeL $abutFoundNodeL $deckNodeR $abutNodeR $abutFoundNodeR -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.abutacc -time  -node  $abutNodes -dof 1 2 3 accel"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.labutforce -time  -ele $deckArrayEleListL globalForces"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.rabutforce -time  -ele $deckArrayEleListR globalForces"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.labutforceLocal -time  -ele $deckArrayEleListL localForces"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.rabutforceLocal -time  -ele $deckArrayEleListR localForces"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.tim -time  -node 1 -dof 1 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.dsp -time  -node $columnNodes $piercapNodes $deckNodes $deckendNodes $abutNodes $soilSpringNodes -dof 1 2 3 disp"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.ifp -time  -ele $columnEles inflectionPoint"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.dft -time  -ele $columnEles tangentDrift"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cfor1 -time  -ele $columnEles section 1 force"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cfor2 -time  -ele $columnEles section 2 force"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cfor3 -time  -ele $columnEles section 3 force"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cfor4 -time  -ele $columnEles section 4 force"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cfor5 -time  -ele $columnEles section 5 force"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cdef1 -time  -ele $columnEles section 1 deformation"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cdef2 -time  -ele $columnEles section 2 deformation"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cdef3 -time  -ele $columnEles section 3 deformation"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cdef4 -time  -ele $columnEles section 4 deformation"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.cdef5 -time  -ele $columnEles section 5 deformation"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.colforce -time  -ele $columnEles localForces"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.colacc -time  -node $columnNodes -dof 1 2 3 accel"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.coldisp -time  -node $columnNodes -dof 1 2 3 4 5 6 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.colbasedisp -time  -node $columnBaseNodes -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.deckdisp -time  -node $deckNodes -dof 1 2 3 disp"
eval "recorder Node $outfmt $OutputDir/A-ELC_0p10g.deckacc -time  -node $deckNodes -dof 1 2 3 accel"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.deckforce -time  -ele $deckEles localForces"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.initYield1 -time  -ele $columnEles section 1 initYield $initYield"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.initYield2 -time  -ele $columnEles section 2 initYield $initYield"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.initYield3 -time  -ele $columnEles section 3 initYield $initYield"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.initYield4 -time  -ele $columnEles section 4 initYield $initYield"
eval "recorder Element $outfmt $OutputDir/A-ELC_0p10g.initYield5 -time  -ele $columnEles section 5 initYield $initYield"

# analysis options
numberer $numberer
eval "system $solver"
test NormDispIncr 1e-05 300 2
constraints Penalty 1e+18 1e+18
set Algorithm "Newton"
algorithm $Algorithm
#integrator LoadControl 1 1 1 1
#analysis Static
rayleigh $am 0.0 $ak 0.0
integrator Newmark $gamma  [expr pow($gamma+0.5, 2)/4]
analysis VariableTransient 

set fileId [open $tracefnameTot "w"]
puts $fileId "2 40.000000"
close $fileId

set fileId [open $tracefnameCurr "w"]
puts $fileId 0
close $fileId

set ok [analyze $numSteps $compdT [expr $compdT/100] $compdT  15]
if {$ok != 0} { return $ok }

set endT [clock seconds]
set ElapsedTime [expr $endT-$startT]
set ElapsedHours [expr int($ElapsedTime/3600.)]
set ElapsedMins [expr int($ElapsedTime/60.-$ElapsedHours*60.)]
set ElapsedSecs [expr int($ElapsedTime-$ElapsedHours*3600-$ElapsedMins*60.)]
puts "
Analysis finished at: [clock format [clock seconds]]"
puts "Execution time: $ElapsedHours hours and $ElapsedMins minutes and $ElapsedSecs seconds."
wipe
