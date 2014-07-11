# coding: utf-8
# [school-tagging] webapp

import objects as objs
import webapp2
import jinja2
import os
import logging
import datetime



class MainHandler(webapp2.RequestHandler):
	template_dir = os.path.join(os.path.dirname(__file__), 'pages')
	jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
		autoescape = True)

	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)
	
	def read(self,param):
		return self.request.get(param)
		
	def renderStr(self, template, **params):
		return self.jinja_env.get_template(template).render(params)
		
	def renderPage(self, template, **kw):
		self.write(self.renderStr(template, **kw))

	def addCookie(self, kind, value):
		self.response.set_cookie(kind, value=str(value), httponly=True)
	
	def getCookie(self, kind):
		return self.request.cookies.get(kind)
	
	def clearCookies(self):
		self.response.delete_cookie("schooltagging-username")
		self.response.delete_cookie("schooltagging-lessonID")
		self.response.delete_cookie("schooltagging-role")
	
	
	def getRoleFromCookie(self):
		return self.getCookie("schooltagging-role")
		
	def getFromCookie(self):
		username = self.getCookie("schooltagging-username")
		lessonStrID = self.getCookie("schooltagging-lessonID")
		role = self.getCookie("schooltagging-role")
		if not username or not role or not lessonStrID:
			return False
		if role == "student":
			user = objs.getStudent(username, int(lessonStrID))
		elif role == "teacher":
			user = objs.getTeacher(username)
		return user

class StartPage(MainHandler):
	def get(self):
		link = None
		user = self.getFromCookie()
		if user and user.currentLessonID:
			lesson = objs.getLesson(user.currentLessonID)
			if lesson:
				if self.getRoleFromCookie() =="teacher":
					link = "/t/dashboard"
				elif self.getRoleFromCookie() == "student":
					link = "/s/dashboard"
		self.renderPage("start.html", resumeDashboardLink=link)
		
class TeacherHandler(MainHandler):
	def get(self, action):
		if action == "dashboard":
			self.initializeDashboard()
		elif action == "logout":
			self.logout()
		elif action == "timeIsUp":
			self.endSession()
		elif action == "askStats":
			self.sendStats()
		else:
			self.renderPage("teacherLogin.html")
	
	def post(self, action):
		if action == "login":
			self.login()
		elif action == "signup":
			self.signup()
		elif action == "askStudentStats":
			self.produceStudentStats(self.read("student"))
	

	def login(self):
		username = self.read("username")
		password = self.read("password")
		if objs.teacherUsernameExists(username):
			teacher = objs.getTeacher(username)
			if password == teacher.password:
				lessonName = self.read("lessonName")
				if lessonName:
					if lessonName not in objs.getOpenLessonsNames():
						teacher.connect()
						self.addCookie("schooltagging-role", "teacher")
						self.addCookie("schooltagging-username", username)
						self.startLesson(teacher)
						return self.redirect("/t/dashboard")
					else:
						message = "Lesson name already in use"
				else:
					message = "Please provide a name for the lesson"
			else:
				message = "Password not correct"
		else:
			message = "Username not existing"
		return self.renderPage("teacherLogin.html", message=message)
		
	def logout(self):
		teacher = self.getFromCookie()
		if teacher:
			self.clearCookies()
			if teacher.currentSession:
				session = objs.getSession(teacher.currentSession)
				if session:
					session.end()
			if teacher.currentLessonID:
				lesson = objs.getLesson(teacher.currentLessonID)
				if lesson:
					lesson.end()
				teacher.logout()
		return self.redirect("/t/login")
	
	def signup(self):
		username = self.read("username")
		if not objs.teacherUsernameExists(username):
			password = self.read("password")
			objs.createTeacher(username, password)
			message = "Please re-enter username and password in the LOGIN area"
		else:
			message = "Username already in use"
		return self.renderPage("teacherLogin.html", message=message)
	
	def startLesson(self, teacher):
		lessonName = self.read("lessonName")
		if lessonName not in objs.getOpenLessonsNames():
			lesson = objs.Lesson()
			lesson.start(lessonName, teacher)
			self.addCookie("schooltagging-lessonID", str(lesson.key.id()))
			return self.redirect("/t/dashboard")
		else:
			message = "Lesson name currently in use"
		return self.renderPage("teacherLogin.html", message=message)
	
	def sendStats(self):
		teacher = self.getFromCookie()
		if not teacher:
			return self.redirect("/t/login")
		if not teacher.currentLessonID:
			return self.redirect("/t/login")
		lesson = objs.getLesson(teacher.currentLessonID)
		if lesson:
			return lesson.produceAndSendStats()
		else:
			return self.redirect("/t/login")
	
	def produceStudentStats(self, studentName):
		teacher = self.getFromCookie()
		if not teacher:
			return self.redirect("/t/login")
		if not teacher.currentLessonID:
			return self.redirect("/t/login")
		student = objs.getStudent(studentName, teacher.currentLessonID)
		if student:
			return student.produceAndSendOwnStats()
		else:
			return self.redirect("/t/login")
		
		
	def initializeDashboard(self):
		teacher = self.getFromCookie()
		if not teacher:
			return self.redirect("/t/login")
		if not teacher.currentLessonID:
			return self.redirect("/t/login")
		lesson = objs.getLesson(teacher.currentLessonID)
		if lesson:
			return self.renderPage("teacherDashboard.html",
							teacherName=teacher.username,
							lessonName=teacher.currentLessonName,
							students=lesson.students,
							token=teacher.token,
							)
		else:
			return self.redirect("/t/login")

	def endSession(self):
		teacher = self.getFromCookie()
		session = objs.getSession(teacher.currentSession)
		if session:
			session.end()

class DataHandler(MainHandler):
	def get(self, kind):
		requester = self.getFromCookie()
		requesterRole = self.getRoleFromCookie()
		if requesterRole == "teacher":
			if kind == "exercise_request":
				lessonID = requester.currentLessonID
				session = objs.Session()
				session.start(lessonID)
	
	def post(self, kind):
		requester = self.getFromCookie()
		requesterRole = self.getRoleFromCookie()
		if requesterRole == "teacher":
			teacher = requester
			if kind == "teacherValidation":
				valid = self.read("valid").strip()
				session = objs.getSession(teacher.currentSession)
				session.addValidAnswer(valid)
				session.sendFeedbackToStudents()
		if requesterRole == "student":
			student = requester
			if kind == "answer":
				answer = self.read("answer").strip()
				student.addAnswer(answer)
				session = objs.getSession(student.currentSession)
				session.addStudentAnswer(student.username, answer)
				session.sendStatusToTeacher()
				
	
class StudentHandler(MainHandler):
	def get(self, action):
		if action == "dashboard":
			self.initializeDashboard()
		elif action == "login":
			self.renderPage("studentLogin.html")
		elif action == "logout":
			self.logout()
		
	def post(self, action):
		if action == "login":
			self.login()
	

	def login(self):
		student = objs.Student()
		student.username = self.read("username")
		lessonName = self.read("lessonName")
		if lessonName in objs.getOpenLessonsNames():
			if not objs.studentAlreadyConnected(student.username, lessonName):
				student.save()
				student.connect()
				self.addCookie("schooltagging-role", "student")
				self.addCookie("schooltagging-username", student.username)
				lessonID = student.joinLesson(lessonName)
				self.addCookie("schooltagging-lessonID", lessonID)
				return self.redirect("/s/dashboard")
			else:
				message = "Name already in use"
		else:
			message = "Lesson not started yet"
		self.renderPage("studentLogin.html", message=message)
		
	def initializeDashboard(self):
		student = self.getFromCookie()
		if not student:
			self.clearCookies()
			return self.redirect("/s/login")
		lesson = student.currentLessonID
		if lesson not in objs.getOpenLessonsID():
			self.clearCookies()
			return self.redirect("/s/login")
		self.renderPage("studentDashboard.html",
							studentName=student.username,
							lessonName=student.currentLessonName,
							token=student.token,
							)
	def logout(self):
		student = self.getFromCookie()
		if student:
			self.clearCookies()
			student.logout()
		return self.redirect("/s/login")
		
class DeleteHandler(MainHandler):
	def get(self):
		objs.clean()
		for name in self.request.cookies.iterkeys():
			self.response.delete_cookie(name)
		return self.redirect("/start")



class ConnectionHandler(MainHandler):
	def post(self, action):
		""" channel service interrupted from yaml"""
		a = self.request.get('from')
		user = objs.getFromID(a)
		if user:
			if user.__class__.__name__ == "Student":
				student = user
				if action == "disconnected":
					return student.alertTeacherImOffline()
# 			elif user.__class__.__name__ == "Teacher":
# 				teacher = user
# 				global TICKTACK
# 				if action == "disconnected":
# 					if teacher.currentLessonID:
# 						lesson = objs.getLesson(teacher.currentLessonID)
# 						TICKTACK = threading.Timer(20, lessonTimeOut,
# 									{"lesson": lesson, "teacher": teacher})
# 						TICKTACK.start()
# 				elif action == "connected" and TICKTACK:
# 					if teacher.currentLessonID:
# 						lesson = objs.getLesson(teacher.currentLessonID)
# 						TICKTACK.cancel()
						

						
class ChannelHandler(MainHandler):
	def get(self):
		requester = self.getFromCookie()
		idle = datetime.datetime.now() - requester.lastAction
		if idle < datetime.timedelta(minutes=objs.MAX_IDLE_ALLOWED):
			return requester.connect()
		else:
			return requester.logout()
		
class PingHandler(MainHandler):
	def post(self):
		requester = self.getFromCookie()
		requesterRole = self.getRoleFromCookie()
		if requesterRole == "teacher":
			teacher = requester
			studentName = self.read("student")
			return teacher.sendPingToStudent(studentName)
		elif requesterRole == "student":
			student = requester
			return student.alertTeacherImAlive()
			
class ForceLogoutStudentHandler(MainHandler):
	def post(self):
		requester = self.getFromCookie()
		requesterRole = self.getRoleFromCookie()
		if requesterRole == "teacher":
			teacher = requester
			studentName = self.read("student")
			student = objs.getStudent(studentName, teacher.currentLessonID)
			if student:
				return student.logout()
		
class ExportPage(MainHandler):
	def get(self):
		data = objs.exportJson()
		return self.write(data)
		
class JollyHandler(MainHandler):
	def get(self, jolly):
		return self.redirect("/start")
	
class HelpHandler(MainHandler):
	def get(self):
		return self.renderPage("helpIndex.html")

class CleanIdle(MainHandler):
	def get(self):
		objs.cleanIdleObjects()

PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
app = webapp2.WSGIApplication([
	webapp2.Route(r'/t/<action>',
			handler = TeacherHandler, name="teacher"),
	webapp2.Route(r'/s/<action>',
			handler = StudentHandler, name="student"),
	webapp2.Route(r'/data/<kind>',
			handler=DataHandler, name="data"),
	webapp2.Route(r'/_ah/channel/<action>/',
			handler=ConnectionHandler, name="connection"),
	("/export", ExportPage),
	("/start", StartPage),
	("/admin/delete", DeleteHandler),
	("/ping", PingHandler),
	("/forceLogoutStudent", ForceLogoutStudentHandler),
	("/help", HelpHandler),
	("/admin/clean", CleanIdle),
	("/channelExpired", ChannelHandler),
	(PAGE_RE, JollyHandler),
			])
