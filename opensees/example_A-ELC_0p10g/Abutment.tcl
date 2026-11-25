# Abutment.tcl --
#
#        Abutment (called from the main .tcl file).
#
#            MSBridge (Beta 1.0.1.20324)
#        OpenSees Analysis of Multi-Span Bridges
#      Copyright (c) 2019 All Rights Reserved.
#
# Units: kN, m
#
# Kevin Mackie, 2008/11/18
# version 1.1.2
# kmackie@mail.ucf.edu
# University of Central Florida
#
# Abutment models
#
# INPUT:
#	1. 	<fcn> text command to direct object action
#	2.	<tag> unique tag (among abutment modules) that identifies object in interpreter
#	3.	<abutArgs> (optional) a list of abutment module-specific input

source AbutmentModel.tcl
package require SDC2010SandAbutment

proc Abutment {fcn tag {abutArgs {}} } {

if { [string compare $fcn "create"] == 0 } {
	# parse abutArgs
	set shift [lindex $abutArgs 0]
	set type [lindex $abutArgs 1]

	# abutments use tagged objects between 600001 and 800000, gives them 20000 tagged objects each
	set ashift 600001
	set aeach 20000
	set base_shift [expr $shift+$ashift+($tag-1)*$aeach]
	
	# if the procedure already exists in tcl space, can recreate the OpenSees domain without
	# redefining the tcl procedure
	set tl [info command AbutObject$tag]
	if { [llength $tl] == 0 } {
		# create modules
		${type}::${type} AbutObject$tag $tag $base_shift [lrange $abutArgs 2 end]
	}
	
    # initialize modules
    AbutObject$tag "initialize"
    
} else {
	# pass method to object for evaluation, no longer depends on the type
	if { [llength $abutArgs] > 0 } {
		set outp [AbutObject$tag $fcn $abutArgs]
	} else {
		set outp [AbutObject$tag $fcn]
	}
    return $outp
}

}
