"""
   Copyright 2010 Greg L. Turnquist, All Rights Reserved

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.       
"""

import cherrypy
import inspect
import logging
import re
import pika
import asyncore
import pickle
import time
import urllib
import cgi

from springpython.security import AuthenticationException
from springpython.security.context import SecurityContextHolder
from springpython.security.providers import UsernamePasswordAuthenticationToken

dojo_dir = "/js/dojo-release-1.4.3"

def header(head_hook="", body_hook=""):
    """Standard header used for all pages"""
    return """
        <!--
        
            Twitter_clone Application :: A twitter_clone application-creating template
        
        -->
        
        <html>
        <head>
        <title>Twitter_clone Application :: A twitter_clone application-creating template</title>
        <style type="text/css">
              @import \"""" + dojo_dir + """/dijit/themes/tundra/tundra.css";
              @import \"""" + dojo_dir + """/dojo/resources/dojo.css";
              body, html { width:95%; height:95%; padding:3px; font-size:100%;}
              label { 
                  width:150px; 
                  float: left;
              }
              table {
                  border-collapse:collapse;
              }
              td {
                  padding:3px;
              }
              table.cmd, tr.cmd, td.cmd { 
                  border: 1px solid black;
              }
              table#footer {
                  width: 100%;
                  font-size:90%;
              }
              .greyedout {
                  text-align: right;
                  color: silver;
              }
              
              div#top {
                  width: 100%;
                  background-color:lightgreen;
                  background-image: url(/images/spring_python_white.png);
                  height:100px;
                  background-repeat: no-repeat;
                  background-position: right;
                  border: solid;
                  border-width: 1px;
              }
        </style>
        <script type="text/javascript" src=\"""" + dojo_dir + """/dojo/dojo.js" djConfig="parseOnLoad: true"></script>
        """ + head_hook + """
        </head>
        
        <body class="tundra" """ + body_hook + """>
            <div id="top"></div>
            """

def footer():
    """Standard footer used for all pages."""
    return """
        <p>
        <hr/>
        <table id="footer"><tr>
                <td><A href="/">Home</A></td>
                <td class="greyedout">Twitter_clone Application :: A <a href="http://cherrypy.org">CherryPy</a>-based Twitter_clone application-creating template</td>
        </tr></table>
        </p>
        </body>
        </html>
        """
    
class Twitter_cloneView(object):
    """Presentation layer of the web application."""

    def __init__(self, poller=None, message_store=None):
        self.logger = logging.getLogger("twitter_clone.view.Twitter_cloneApp")
        self.time_format = "%a, %d %b %Y %H:%M:%S +0000"
        self.counter = 2
        self.poller = poller
        self.message_store = message_store
        
    @cherrypy.expose
    def index(self, notice=""):
        """This is the root page for your twitter_clone app. Its default includes links to all other exposed
           links automatically."""
        return header() + """
            <H2>Welcome to Twitter_clone</H2> 
            <h3>%s</h3>
            <table class="cmd">
            <P>""" % notice + "".join(['\n\t\t<tr class="cmd">\n\t\t\t<td class="cmd"><a href="%s">%s</a></td>\n\t\t\t<td class="cmd">%s</td>\n\t\t</tr>\n' % (name, name, method.__doc__)
		for (name, method) in inspect.getmembers(self, inspect.ismethod)
		if hasattr(method, "exposed") and name != "index"]) + """
            </table>
        """ + footer()

    @cherrypy.expose
    def dojo_demo(self):
        """This is a sandbox for doing dojo development."""
        return header(head_hook="""
    <script type="text/javascript">
          dojo.require("dojo.parser");
          dojo.require("dijit.Dialog");
          dojo.require("dijit.layout.BorderContainer");
          dojo.require("dijit.layout.ContentPane");
          dojo.require("dijit.layout.TabContainer");
          dojo.require("dijit.form.ValidationTextBox");
    </script>
    """) + """
    <div dojoType="dijit.layout.TabContainer" style="width:100%;height:75%;">
        <div dojoType="dijit.layout.ContentPane" title="Login">
            <form method="POST" action="">
                <label for="login">Login:</label>
                <input type="text" name="login" size="10" dojoType="dijit.form.ValidationTextBox"
                                            trim="true" required="true" promptMessage="Enter your username"/><br/>
                <label for="password">Password:</label>
                <input type="password" name="password" size="10" dojoType="dijit.form.ValidationTextBox"
                                            trim="true" required="true" promptMessage="Enter your password"/><br/>
                <input type="hidden" name="fromPage" value="%s"/><br/>
                <input type="submit"/>
            </form>

        </div>

        <div dojoType="dijit.layout.ContentPane" title="Stuff">
            More content
        </div>

        <div dojoType="dijit.layout.ContentPane" title="More Stuff">
            <form method="GET" action="">
                <label for="foobar">Foobar:</label>
                <input type="text" name="foobar" dojoType="dijit.form.ValidationTextBox" trim="true" required="true" promptMessage="Enter foobar"/><br/>
            </form>
        </div>
    </div>
</body>
</html> """ + footer()

    @cherrypy.expose
    def messages(self, i_have="0"):
        """This web service is used to serve Ajax requests for data"""
        num = 5
        i_have = int(i_have)
        if i_have >= len(self.message_store.get_data()):
            return "<response/>"
            #raise cherrypy.HTTPError(404)
        return "<response>" + "".join(['<message user="%s" date="%s">%s</message>' % (id,date,m) for (m,id,date) in self.python_messages(i_have, num)]) + "</response>"

    def python_messages(self, i_have, num):
        return self.message_store.get_data()[i_have:]

    @cherrypy.expose
    def chat(self):
        """This javascript experiment is meant to create a twitter-like way of reading/writing messages."""
        return header(head_hook="""
            <script type="text/javascript">
                // Set up some variables to support running a repeating timer, and avoiding multiple timers 
                var c = 0
                var t
                var timer_is_on = 0

                // This function is meant to periodically poll for new chat messages, and then insert them into a particular paragraph on the page.
                function loadChats() {
                    // Set things up for an ajax-style call to fetch data.
                    if (window.XMLHttpRequest) {
                        xmlhttp = new XMLHttpRequest()
                    } else {
                        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP")
                    }

                    xmlhttp.onreadystatechange = function() {
                        if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
                            // Since the response is an XML strong, and not an XML document, run a DOM parser to turn it into a Document.
                            if (window.DOMParser) {
                                parser = new DOMParser()
                                xmlDoc = parser.parseFromString(xmlhttp.responseText, "text/xml")
                            } else {
                                xmlDoc = new ActiveXObject("Microsoft.XMLDOM")
                                xmlDoc.async = "false"
                                xmlDoc.loadXML(xmlhttp.reponseText)
                            }

                            // Grab a handle on the box where messages will be inserted
                            var box = document.getElementById("message_box")
                            //box.innerHTML = ""

                            // Pull out all the <message> tags, and then iterate over each one, displaying them top-to-bottom in the box.
                            x = xmlDoc.getElementsByTagName("message")
                            for (i=0; i<x.length; i++) {
                                box.innerHTML = "<tr id='rows'><td>" + x[i].childNodes[0].nodeValue + "</td><td>" + x[i].attributes.getNamedItem("user").nodeValue + "</td><td>" + x[i].attributes.getNamedItem("date").nodeValue + "</td></tr>" + box.innerHTML
                            }

                            // Increment an internal counter, and then schedule this job to run again
                            c += x.length
                            t = setTimeout("loadChats()", 1000)
                        } else if (xmlhttp.status == 404) {
                            t = setTimeout("loadChats()", 5000)
                        }
                    }

                    // Make the web call to messages to grab the latest round of messages, packaged in XML format
                    xmlhttp.open("GET", "/messages?i_have="+c, true)
                    xmlhttp.send()
                }

                // This function blocks the timer from running more than one instance.
                function doTimer() {
                    if (!timer_is_on) {
                        timer_is_on = 1
                        loadChats()
                    }
                }
            </script>""", body_hook='onload="doTimer()"') + """
                <p/>
                <form name="input" action="new_message" method="get">
                    <label for="input">Message:</label>
                    <input text="text" name="message"/>
                    <input type="submit" value="Submit"/>
                </form>
                <p/>
                <table id="message_box"> </table>
                <p/>
        """ + footer()

    @cherrypy.expose
    def new_message(self, message="This is a sample twitter message."):
        """Send a new message"""
        message = (message, SecurityContextHolder.getContext().authentication.username, time.strftime(self.time_format, time.gmtime()))
        #message = (message, "jcoleman", time.strftime(self.time_format, time.gmtime()))
        pickled_message = pickle.dumps(message)
        try:
            self.poller.send_message(pickled_message)
        except Exception, e:
            self.logger.error(e)
            raise self.redirectStrategy.redirect("/?notice=%s" % urllib.quote("Failed to send message"))
        #self.append_message(pickled_message)
        raise cherrypy.HTTPRedirect("/chat")

    @cherrypy.expose
    def append_message(self, pickled_message):
        """This increments the counter and then appends the message to the data set."""
        self.counter += 1
        self.message_store.append(pickle.loads(pickled_message))

    @cherrypy.expose
    def admin(self):
	"""This page will provide some administrative functionality"""
        return self.under_dev()

    @cherrypy.expose
    def user_management(self):
        """Define users"""
        return self.under_dev()

    @cherrypy.expose
    def role_management(self):
        "Define roles"
        return self.under_dev()

    def under_dev(self):
        return header() + "This page is under development" + footer()

    @cherrypy.expose
    def login(self, fromPage="/", login="", password="", errorMsg=""):
        """Login to the web app"""
        if login != "" and password != "":
            try:
                self.attemptAuthentication(login, password)
                return [self.redirectStrategy.redirect(fromPage)]
            except AuthenticationException, e:
                return [self.redirectStrategy.redirect("?login=%s&errorMsg=Username/password failure" % login)]

        # Display hard-coded, unhashed passwords. NOTE: These cannot be retrieved from
        # the application context, because they are one way hashes. This must be kept
        # in sync with the application context.
        results = header(head_hook = """
            <script type="text/javascript">
                dojo.require("dojo.parser")
                dojo.require("dijit.form.ValidationTextBox")
                dojo.require("dijit.layout.ContentPane")
                dojo.require("dijit.layout.TabContainer")
            </script>
        """)

        results += """
            <div dojoType="dijit.layout.TabContainer" style="width:100%;height:50%">
        """

        results += """
                <div dojoType="dijit.layout.ContentPane" title="Login">
                    <form method="POST" action="">
                        <label for="login">Login:</label>
                        <input type="text" name="login" value="%s" size="10" dojoType="dijit.form.ValidationTextBox" 
                                                    trim="true" required="true" missingMessage="Enter your username"/><br/>
                        <label for="password">Password:</label>
                        <input type="password" name="password" size="10" dojoType="dijit.form.ValidationTextBox"
                                                    trim="true" required="true" missingMessage="Enter your password"/><br/>
                        <input type="hidden" name="fromPage" value="%s"/><br/>
                        <input type="submit"/>
                    </form>
                </div>
        """ % (login, fromPage)
 
        results += self.demo_passwords()   # Remove this step to stop displaying sample users

        results += """
        </div>"""

        results += footer()
        return [results]

    def demo_passwords(self):
        results = """
            <div dojoType="dijit.layout.ContentPane" title="Sample passwords">
            <h4>Hashed passwords - <small>The following tables contain accounts that are stored with one-way hashes.</small></h4>
            <p>
        """
        for hashedUserDetailsService in self.hashedUserDetailsServiceList:
            results += """
                <small>%s</small>
                <table border="1" cellspacing="0">
                    <tr>
                        <th><small>Username</small></th>
                        <th><small>Password</small></th>
                        <th><small>Granted authorities</small></th>
                        <th><small>Enabled?</small></th>
                    </tr>
                """ % cgi.escape(str(hashedUserDetailsService))
            for key, value in hashedUserDetailsService.wrappedUserDetailsService.user_dict.items():
                    results += """
                    <tr>
                        <td><small>%s </small></td>
                        <td><small>%s </small></td>
                        <td><small>%s </small></td>
                        <td><small>%s </small></td>
                    </tr>
                """ % (key, value[0], value[1], value[2])
            results += """
                </table>
                <p />
                </div>
            """
        return results

    @cherrypy.expose    
    def logout(self):
        """Replaces current authentication token, with an empty, non-authenticated one."""
        self.filter.logout()
	self.httpContextFilter.saveContext()
        raise cherrypy.HTTPRedirect("/")

    def attemptAuthentication(self, username, password):
        """Authenticate a new username/password pair using the authentication manager."""
        self.logger.debug("Trying to authenticate %s using the authentication manager" % username)
        token = UsernamePasswordAuthenticationToken(username, password)
        SecurityContextHolder.getContext().authentication = self.authenticationManager.authenticate(token)
	self.httpContextFilter.saveContext()
        self.logger.debug(SecurityContextHolder.getContext())


