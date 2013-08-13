/*******************************
 *
 * geolocation.js: GeoLocation support for the SnipDex Web Client.
 *
 * Copyright (C) 2010 Almer S. Tigelaar
 *
 */

/*
 * TODO: This should actually be tested on a WIFI connection.
 * TODO: This only supports the 'standard' html5 of geolocating (not alternative API's).
 *       There are some nice wrappers for that though ...
 *
 * TODO: 
 */

var watchID = -1;

function add_geo_nodes() {
    var search_form = document.getElementById('snipdex');
    var latitude    = document.createElement('input');
    var longitude   = document.createElement('input');

    latitude.setAttribute('name', 'latitude');
    latitude.setAttribute('id', 'latitude');
    latitude.setAttribute('type', 'hidden');
    latitude.setAttribute('value', '0.0');

    longitude.setAttribute('name', 'longitude');
    longitude.setAttribute('id', 'longitude');
    longitude.setAttribute('type', 'hidden');
    longitude.setAttribute('value', '0.0');

    search_form.appendChild(latitude);
    search_form.appendChild(longitude);
}

function remove_geo_nodes() {
    var search_form = document.getElementById('snipdex');
    var latitude    = document.getElementById('latitude');
    var longitude   = document.getElementById('longitude');

    search_form.removeChild(latitude);
    search_form.removeChild(longitude);

    var heading = document.getElementById('heading');
    if (heading != null) {
	search_form.removeChild(heading);
    }
    var altitude = document.getElementById('altitude');
    if (altitude != null) {
	search_form.removeChild(altitude);
    }
    var accuracy = document.getElementById('accuracy');
    if (accuracy != null) {
	search_form.removeChild(accuracy);
    }
    var altitudeAccuracy = document.getElementById('altitudeAccuracy');
    if (altitudeAccuracy != null) {
	search_form.removeChild(altitudeAccuracy);
    }
}

function update_position(position) {
    var search_form = document.getElementById('snipdex');
    var latitude  = document.getElementById('latitude');
    var longitude = document.getElementById('longitude');

    latitude.setAttribute('value', position.coords.latitude);
    longitude.setAttribute('value', position.coords.longitude);

    if (position.coords.heading != null) {
	var heading = document.getElementById('heading');
	if (heading == null) { /* Create dynamically if it does not exist yet */
	    var heading = document.createElement('heading');
	    heading.setAttribute('name', 'heading');
	    heading.setAttribute('id', 'heading');
	    heading.setAttribute('type', 'hidden');
	    search_form.appendChild(heading);
	}
	heading.setAttribute('value', position.coords.heading);
    }
    if (position.coords.altitude != null) {
	var altitude = document.getElementById('altitude');
	if (altitude == null) { /* Create dynamically if it does not exist yet */
	    var altitude = document.createElement('altitude');
	    altitude.setAttribute('name', 'altitude');
	    altitude.setAttribute('id', 'altitude');
	    altitude.setAttribute('type', 'hidden');
	    search_form.appendChild(altitude);
	}
	altitude.setAttribute('value', position.coords.altitude);
    }
    if (position.coords.accuracy != null) {
	var accuracy = document.getElementById('accuracy');
	if (accuracy == null) { /* Create dynamically if it does not exist yet */
	    var accuracy = document.createElement('accuracy');
	    accuracy.setAttribute('name', 'accuracy');
	    accuracy.setAttribute('id', 'accuracy');
	    accuracy.setAttribute('type', 'hidden');
	    search_form.appendChild(accuracy);
	}
	accuracy.setAttribute('value', position.coords.accuracy);
    }
    if (position.coords.altitudeAccuracy != null) {
	var altitudeAccuracy = document.getElementById('altitudeAccuracy');
	if (altitudeAccuracy == null) { /* Create dynamically if it does not exist yet */
	    var altitudeAccuracy = document.createElement('altitudeAccuracy');
	    altitudeAccuracy.setAttribute('name', 'altitudeAccuracy');
	    altitudeAccuracy.setAttribute('id', 'altitudeAccuracy');
	    altitudeAccuracy.setAttribute('type', 'hidden');
	    search_form.appendChild(altitudeAccuracy);
	}
	altitudeAccuracy.setAttribute('value', position.coords.altitudeAccuracy);
    }
}

function enable_geolocation() {
    if (navigator.geolocation) {  
	add_geo_nodes()
	watchID = navigator.geolocation.watchPosition(update_position);  
    }
}

function disable_geolocation() {
    if (navigator.geolocation) {  
	navigator.geolocation.clearWatch(watchID);
	remove_geo_nodes();
	watchID = -1;
    }
}

function toggle_geolocation() {
    if (watchID == -1) {
	enable_geolocation();
    } else {
	disable_geolocation();
    }
}

function get_geolocation_label() {
    if (watchID == -1) {
	return 'Disable GeoLocation';
    } else {
	return 'Enable GeoLocation';
    }
}